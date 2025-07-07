-- Create customers table
CREATE TABLE customers (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL
);

-- Create products table
CREATE TABLE products (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    category TEXT
);

-- Create orders table (to link customers and products)
CREATE TABLE orders (
    id INTEGER PRIMARY KEY,
    customer_id INTEGER,
    product_id INTEGER,
    order_date TEXT,
    FOREIGN KEY (customer_id) REFERENCES customers(id),
    FOREIGN KEY (product_id) REFERENCES products(id)
);

-- Insert sample customers
INSERT INTO customers (name) VALUES
('Alice Smith'),
('Bob Johnson');

-- Insert sample products
INSERT INTO products (name, category) VALUES
('Laptop', 'Electronics'),
('Headphones', 'Electronics'),
('Coffee Mug', 'Home'),
('Notebook', 'Stationery');

-- Insert sample orders
INSERT INTO orders (customer_id, product_id, order_date) VALUES
(1, 1, '2024-01-10'),  -- Alice bought Laptop
(1, 4, '2024-01-15'),  -- Alice bought Notebook
(2, 2, '2024-01-12');  -- Bob bought Headphones