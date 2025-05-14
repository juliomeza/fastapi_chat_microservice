from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import text
import re

async def query_database(db: AsyncSession, query_type: str, message: str, project_project_name: str, user_id: str) -> str:
    """
    Queries the PostgreSQL database.
    IMPORTANT: Adapt SQL queries to your actual database schema.
    """
    if query_type == "order_status":
        try:
            # Determinar si se busca un estado específico o un conteo general
            order_status_id = None
            if re.search(r'\b(pendiente|pending)\b', message, re.IGNORECASE):
                order_status_id = 1  # ID para 'pendiente'
            elif re.search(r'\b(completada|completed)\b', message, re.IGNORECASE):
                order_status_id = 2  # Suponiendo que ID 2 es para órdenes completadas
            elif re.search(r'\b(cancelada|canceled)\b', message, re.IGNORECASE):
                order_status_id = 3  # Suponiendo que ID 3 es para órdenes canceladas
            
            # Si se especifica un estado, hacemos consulta por ese estado
            if order_status_id is not None:
                stmt = text("""
                    SELECT COUNT(*) FROM data_testdata
                    WHERE order_status_id = :order_status_id AND lookup_code = :lookup_code
                """)
                result = await db.execute(stmt, {"order_status_id": order_status_id, "lookup_code": project_project_name})
                count = result.scalar_one_or_none()
                
                if count is not None:
                    status_name = {1: "pendiente", 2: "completada", 3: "cancelada"}.get(order_status_id, f"con estado ID {order_status_id}")
                    return f"Hay {count} órdenes {status_name}s para '{project_project_name}' en 'data_testdata'."
                else:
                    return f"No se pudieron contar las órdenes para '{project_project_name}' en 'data_testdata'."
            
            # Si no se especifica estado, consultamos un resumen de todos los estados
            else:
                stmt = text("""
                    SELECT order_status_id, COUNT(*) as count 
                    FROM data_testdata
                    WHERE lookup_code = :lookup_code
                    GROUP BY order_status_id
                    ORDER BY order_status_id
                """)
                result = await db.execute(stmt, {"lookup_code": project_project_name})
                status_counts = result.fetchall()
                
                if status_counts:
                    status_names = {1: "pendiente", 2: "completada", 3: "cancelada"}
                    response_lines = [f"Resumen de órdenes para '{project_project_name}':"]
                    
                    for row in status_counts:
                        status_id = row.order_status_id
                        count = row.count
                        status_name = status_names.get(status_id, f"con estado ID {status_id}")
                        response_lines.append(f"- {count} órdenes {status_name}s")
                    
                    return "\n".join(response_lines)
                else:
                    return f"No se encontraron órdenes para '{project_project_name}' en 'data_testdata'."
        
        except Exception as e:
            print(f"Database query error for order_status with data_testdata: {e}")
            return f"Error al consultar la base de datos (data_testdata) sobre órdenes para '{project_project_name}'. Detalles: {e}"

    elif query_type == "data_card_report":
        try:
            # Analizamos si se busca información específica
            specific_description = None
            limit_count = 5  # Valor por defecto
            
            # Buscar solicitud para más resultados
            limit_match = re.search(r'(\d+)\s+(?:reportes|reports)', message, re.IGNORECASE)
            if limit_match:
                try:
                    limit_count = int(limit_match.group(1))
                    # Establecemos un límite razonable para evitar sobrecarga
                    if limit_count > 20:
                        limit_count = 20
                except ValueError:
                    pass
            
            # Buscar si se menciona alguna descripción específica
            desc_pattern = r'(?:sobre|acerca de|para|about)\s+["\']?([^"\']+)["\']?'
            desc_match = re.search(desc_pattern, message, re.IGNORECASE)
            if desc_match:
                specific_description = desc_match.group(1).strip()
            
            # Construir consulta según el caso
            if specific_description:
                stmt = text("""
                    SELECT description, total, day1_value, day2_value, day3_value, 
                           day4_value, day5_value, day6_value, day7_value
                    FROM data_datacardreport
                    WHERE warehouse = :warehouse_name 
                      AND description ILIKE :desc_pattern
                    ORDER BY year DESC, week DESC
                    LIMIT :limit_count
                """)
                result = await db.execute(stmt, {
                    "warehouse_name": project_project_name,
                    "desc_pattern": f"%{specific_description}%",
                    "limit_count": limit_count
                })
            else:
                stmt = text("""
                    SELECT description, total, day1_value, day7_value 
                    FROM data_datacardreport
                    WHERE warehouse = :warehouse_name
                    ORDER BY year DESC, week DESC, section, list_order
                    LIMIT :limit_count
                """)
                result = await db.execute(stmt, {
                    "warehouse_name": project_project_name,
                    "limit_count": limit_count
                })
            
            reports = result.fetchall()
            
            if not reports:
                if specific_description:
                    return f"No se encontraron reportes que coincidan con '{specific_description}' para '{project_project_name}'."
                else:
                    return f"No se encontraron reportes para '{project_project_name}'."
            
            # Formatear respuesta según el caso
            if specific_description:
                response_lines = [f"Reportes relacionados con '{specific_description}' para '{project_project_name}':"]
                for report_row in reports:
                    response_lines.append(f"- {report_row.description}")
                    response_lines.append(f"  Total: {report_row.total}")
                    days = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
                    day_values = [
                        report_row.day1_value, report_row.day2_value, report_row.day3_value,
                        report_row.day4_value, report_row.day5_value, report_row.day6_value, 
                        report_row.day7_value
                    ]
                    day_info = []
                    for i, (day, value) in enumerate(zip(days, day_values)):
                        if value is not None:
                            day_info.append(f"{day}: {value}")
                    response_lines.append("  " + ", ".join(day_info))
            else:
                response_lines = [f"{len(reports)} reportes recientes para '{project_project_name}':"]
                for report_row in reports:
                    response_lines.append(f"- {report_row.description}")
                    response_lines.append(f"  Total: {report_row.total}, Lunes: {report_row.day1_value}, Domingo: {report_row.day7_value}")
            
            return "\n".join(response_lines)
        except Exception as e:
            print(f"Database query error for data_card_report: {e}")
            return f"Error al consultar 'data_datacardreport' para '{project_project_name}'. Detalles: {e}"

    elif query_type == "customer_info":
        try:
            # This query type has not yet been adapted for 'data_testdata' or 'data_datacardreport'.
            return f"La consulta de información de clientes para '{project_project_name}' aún no se ha adaptado a las nuevas tablas. (Implementación pendiente)"
        except Exception as e:
            print(f"Database query error for customer_info: {e}")
            return f"Error al procesar la consulta de información de clientes para '{project_project_name}'. Detalles: {e}"

    elif query_type == "schema_info":
        try:
            # Determinamos qué tabla está solicitando el usuario
            table_name = None
            if re.search(r'\b(data_testdata|testdata)\b', message, re.IGNORECASE):
                table_name = "data_testdata"
            elif re.search(r'\b(data_datacardreport|datacardreport|card|report)\b', message, re.IGNORECASE):
                table_name = "data_datacardreport"
            
            # Si se especifica una tabla, mostrar su estructura
            if table_name:
                stmt = text("""
                    SELECT column_name, data_type, is_nullable 
                    FROM information_schema.columns 
                    WHERE table_name = :table_name 
                    ORDER BY ordinal_position
                """)
                result = await db.execute(stmt, {"table_name": table_name})
                columns = result.fetchall()
                
                if columns:
                    response_lines = [f"Estructura de la tabla '{table_name}':"]
                    response_lines.append("| Columna | Tipo de dato | ¿Permite nulos? |")
                    response_lines.append("|---------|-------------|----------------|")
                    
                    for col in columns:
                        nullable = "Sí" if col.is_nullable == "YES" else "No"
                        response_lines.append(f"| {col.column_name} | {col.data_type} | {nullable} |")
                    
                    return "\n".join(response_lines)
                else:
                    return f"No se pudo obtener información sobre la estructura de la tabla '{table_name}'."
            
            # Si no se especifica una tabla, mostrar las tablas disponibles
            else:
                return """Las tablas disponibles son:
                
1. data_testdata - Contiene información sobre órdenes y sus estados
   - order_id: ID único de la orden
   - order_class_id: ID de la clase de orden
   - order_status_id: ID del estado de la orden (1=pendiente, 2=completada, 3=cancelada)
   - fetched_at: Fecha y hora de recuperación
   - lookup_code: Código de búsqueda (coincide con el proyecto)

2. data_datacardreport - Contiene reportes y estadísticas
   - warehouse: Nombre del almacén (coincide con el proyecto)
   - description: Descripción del reporte
   - total: Valor total
   - day1_value a day7_value: Valores diarios (Lunes a Domingo)
   - year, week: Año y semana del reporte
   - Y otros campos de metadatos

¿Sobre cuál tabla deseas más información?"""
        except Exception as e:
            print(f"Database query error for schema_info: {e}")
            return f"Error al consultar información del esquema de la base de datos. Detalles: {e}"

    return f"Respuesta de la base de datos para '{project_project_name}': (Consulta para '{query_type}' no implementada o no adaptada a las nuevas tablas)"
