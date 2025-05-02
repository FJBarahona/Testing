from flask import Flask, render_template, request, redirect, url_for, flash, make_response
import psycopg2
from psycopg2 import sql
from psycopg2.extras import DictCursor
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

app = Flask(__name__)
app.secret_key = 'supersecretkey'  

DB_CONFIG = {
    'host': 'localhost',
    'database': 'facturacion_db',
    'user': 'postgres',
    'password': 'root'
}

def get_db_connection():
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        return conn
    except psycopg2.Error as e:
        print(f"Error al conectar a la base de datos: {e}")
        return None

@app.route('/')
def index():
    return redirect(url_for('listar_facturas'))

@app.route('/facturas')
def listar_facturas():
    conn = get_db_connection()
    if conn is None:
        flash('Error al conectar a la base de datos.')
        return render_template('error.html')
    
    try:
        cur = conn.cursor(cursor_factory=DictCursor)
        cur.execute('SELECT f.id, f.numero, f.fecha, c.nombre as cliente, f.total FROM facturas f JOIN clientes c ON f.cliente_id = c.id ORDER BY f.fecha DESC;')
        facturas = cur.fetchall()
        cur.close()
    except psycopg2.Error as e:
        flash(f'Error al obtener las facturas: {e}')
        return render_template('error.html')
    finally:
        conn.close()
    
    return render_template('facturas.html', facturas=facturas)

@app.route('/factura/nueva', methods=['GET', 'POST'])
def nueva_factura():
    if request.method == 'POST':
        cliente_id = request.form['cliente_id']
        items = []
        total = 0
        
        for i in range(1, 6):  
            producto_id = request.form.get(f'producto_id_{i}')
            cantidad = request.form.get(f'cantidad_{i}')
            if producto_id and cantidad:
                conn = get_db_connection()
                if conn is None:
                    flash('Error al conectar a la base de datos.')
                    return render_template('error.html')
                
                try:
                    cur = conn.cursor()
                    cur.execute('SELECT precio FROM productos WHERE id = %s;', (producto_id,))
                    precio = cur.fetchone()[0]
                    subtotal = float(precio) * float(cantidad)
                    items.append({
                        'producto_id': producto_id,
                        'cantidad': cantidad,
                        'precio': precio,
                        'subtotal': subtotal
                    })
                    total += subtotal
                    cur.close()
                except psycopg2.Error as e:
                    flash(f'Error al obtener el precio del producto: {e}')
                    return render_template('error.html')
                finally:
                    conn.close()
        
        conn = get_db_connection()
        if conn is None:
            flash('Error al conectar a la base de datos.')
            return render_template('error.html')
        
        try:
            cur = conn.cursor()
            cur.execute("SELECT nextval('factura_numero_seq')")
            numero_factura = f"FACT-{cur.fetchone()[0]}"
            
            cur.execute(
                'INSERT INTO facturas (numero, cliente_id, total) VALUES (%s, %s, %s) RETURNING id;',
                (numero_factura, cliente_id, total)
            )
            factura_id = cur.fetchone()[0]
            
            for item in items:
                cur.execute(
                    'INSERT INTO factura_items (factura_id, producto_id, cantidad, precio, subtotal) VALUES (%s, %s, %s, %s, %s);',
                    (factura_id, item['producto_id'], item['cantidad'], item['precio'], item['subtotal'])
                )
            
            conn.commit()
            cur.close()
        except psycopg2.Error as e:
            flash(f'Error al insertar la factura: {e}')
            return render_template('error.html')
        finally:
            conn.close()
        
        return redirect(url_for('ver_factura', id=factura_id))
    
    else:
        conn = get_db_connection()
        if conn is None:
            flash('Error al conectar a la base de datos.')
            return render_template('error.html')
        
        try:
            cur = conn.cursor(cursor_factory=DictCursor)
            cur.execute('SELECT id, nombre FROM clientes ORDER BY nombre;')
            clientes = cur.fetchall()
            
            cur.execute('SELECT id, nombre, precio FROM productos ORDER BY nombre;')
            productos = cur.fetchall()
            
            cur.close()
        except psycopg2.Error as e:
            flash(f'Error al obtener los datos: {e}')
            return render_template('error.html')
        finally:
            conn.close()
        
        return render_template('nueva_factura.html', clientes=clientes, productos=productos)

@app.route('/factura/<int:id>')
def ver_factura(id):
    conn = get_db_connection()
    if conn is None:
        flash('Error al conectar a la base de datos.')
        return render_template('error.html')
    
    try:
        cur = conn.cursor(cursor_factory=DictCursor)
        cur.execute('''
            SELECT f.id, f.numero, f.fecha, f.total, c.id as cliente_id, c.nombre as cliente_nombre, 
                   c.direccion as cliente_direccion, c.telefono as cliente_telefono
            FROM facturas f JOIN clientes c ON f.cliente_id = c.id WHERE f.id = %s;
        ''', (id,))
        factura = cur.fetchone()
        
        cur.execute('''
            SELECT fi.id, p.nombre as producto, fi.cantidad, fi.precio, fi.subtotal
            FROM factura_items fi JOIN productos p ON fi.producto_id = p.id
            WHERE fi.factura_id = %s;
        ''', (id,))
        items = cur.fetchall()
        
        cur.close()
    except psycopg2.Error as e:
        flash(f'Error al obtener la factura: {e}')
        return render_template('error.html')
    finally:
        conn.close()
    
    return render_template('ver_factura.html', factura=factura, items=items)

@app.route('/factura/editar/<int:id>', methods=['GET', 'POST'])
def editar_factura(id):
    conn = get_db_connection()
    if conn is None:
        flash('Error al conectar a la base de datos.')
        return render_template('error.html')
    
    if request.method == 'POST':
        cliente_id = request.form['cliente_id']
        items = []
        total = 0
        
        for i in range(1, 6): 
            producto_id = request.form.get(f'producto_id_{i}')
            cantidad = request.form.get(f'cantidad_{i}')
            if producto_id and cantidad:
                cur = conn.cursor()
                cur.execute('SELECT precio FROM productos WHERE id = %s;', (producto_id,))
                precio = cur.fetchone()[0]
                subtotal = float(precio) * float(cantidad)
                items.append({
                    'producto_id': producto_id,
                    'cantidad': cantidad,
                    'precio': precio,
                    'subtotal': subtotal
                })
                total += subtotal
                cur.close()
        
        try:
            cur = conn.cursor()
            cur.execute(
                'UPDATE facturas SET cliente_id = %s, total = %s WHERE id = %s;',
                (cliente_id, total, id)
            )
            
            cur.execute('DELETE FROM factura_items WHERE factura_id = %s;', (id,))
            
            for item in items:
                cur.execute(
                    'INSERT INTO factura_items (factura_id, producto_id, cantidad, precio, subtotal) VALUES (%s, %s, %s, %s, %s);',
                    (id, item['producto_id'], item['cantidad'], item['precio'], item['subtotal'])
                )
            
            conn.commit()
            cur.close()
        except psycopg2.Error as e:
            flash(f'Error al actualizar la factura: {e}')
            return render_template('error.html')
        finally:
            conn.close()
        
        return redirect(url_for('ver_factura', id=id))
    
    else:
        try:
            cur = conn.cursor(cursor_factory=DictCursor)
            cur.execute('SELECT id, nombre FROM clientes ORDER BY nombre;')
            clientes = cur.fetchall()
            
            cur.execute('SELECT id, nombre, precio FROM productos ORDER BY nombre;')
            productos = cur.fetchall()
            
            cur.execute('''
                SELECT f.id, f.numero, f.fecha, f.total, c.id as cliente_id, c.nombre as cliente_nombre
                FROM facturas f JOIN clientes c ON f.cliente_id = c.id WHERE f.id = %s;
            ''', (id,))
            factura = cur.fetchone()
            
            cur.execute('''
                SELECT fi.id, p.nombre as producto, fi.cantidad, fi.precio, fi.subtotal
                FROM factura_items fi JOIN productos p ON fi.producto_id = p.id
                WHERE fi.factura_id = %s;
            ''', (id,))
            items = cur.fetchall()
            
            cur.close()
        except psycopg2.Error as e:
            flash(f'Error al obtener los datos: {e}')
            return render_template('error.html')
        finally:
            conn.close()
        
        return render_template('editar_factura.html', clientes=clientes, productos=productos, factura=factura, items=items)

@app.route('/factura/eliminar/<int:id>', methods=['POST'])
def eliminar_factura(id):
    conn = get_db_connection()
    if conn is None:
        flash('Error al conectar a la base de datos.')
        return render_template('error.html')
    
    try:
        cur = conn.cursor()
        cur.execute('DELETE FROM factura_items WHERE factura_id = %s;', (id,))
        cur.execute('DELETE FROM facturas WHERE id = %s;', (id,))
        conn.commit()
        cur.close()
    except psycopg2.Error as e:
        flash(f'Error al eliminar la factura: {e}')
        return render_template('error.html')
    finally:
        conn.close()
    
    return redirect(url_for('listar_facturas'))

@app.route('/factura/pdf/<int:id>')
def exportar_factura_pdf(id):
    conn = get_db_connection()
    if conn is None:
        flash('Error al conectar a la base de datos.')
        return render_template('error.html')
    
    try:
        cur = conn.cursor(cursor_factory=DictCursor)
        cur.execute('''
            SELECT f.id, f.numero, f.fecha, f.total, c.id as cliente_id, c.nombre as cliente_nombre, 
                   c.direccion as cliente_direccion, c.telefono as cliente_telefono
            FROM facturas f JOIN clientes c ON f.cliente_id = c.id WHERE f.id = %s;
        ''', (id,))
        factura = cur.fetchone()
        
        cur.execute('''
            SELECT fi.id, p.nombre as producto, fi.cantidad, fi.precio, fi.subtotal
            FROM factura_items fi JOIN productos p ON fi.producto_id = p.id
            WHERE fi.factura_id = %s;
        ''', (id,))
        items = cur.fetchall()
        
        cur.close()
    except psycopg2.Error as e:
        flash(f'Error al obtener la factura: {e}')
        return render_template('error.html')
    finally:
        conn.close()
    
    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    
    p.drawString(100, height - 100, f"Factura #{factura['numero']}")
    p.drawString(100, height - 120, f"Fecha: {factura['fecha']}")
    p.drawString(100, height - 140, f"Cliente: {factura['cliente_nombre']}")
    p.drawString(100, height - 160, f"Dirección: {factura['cliente_direccion']}")
    p.drawString(100, height - 180, f"Teléfono: {factura['cliente_telefono']}")
    
    y = height - 220
    p.drawString(100, y, "Producto")
    p.drawString(300, y, "Cantidad")
    p.drawString(400, y, "Precio Unitario")
    p.drawString(500, y, "Subtotal")
    
    y -= 20
    for item in items:
        p.drawString(100, y, item['producto'])
        p.drawString(300, y, str(item['cantidad']))
        p.drawString(400, y, f"S/.{item['precio']:.2f}")
        p.drawString(500, y, f"S/.{item['subtotal']:.2f}")
        y -= 20
    
    p.drawString(400, y - 20, "Total:")
    p.drawString(500, y - 20, f"S/.{factura['total']:.2f}")
    
    p.showPage()
    p.save()
    
    buffer.seek(0)
    response = make_response(buffer.read())
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename=factura_{factura["numero"]}.pdf'
    
    return response

if __name__ == '__main__':
    app.run(debug=True)
