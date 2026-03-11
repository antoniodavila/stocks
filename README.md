# Stock Analyzer Platform

Plataforma de análisis bursátil que combina análisis estacional, value screening y backtesting para generar señales de inversión de alta convicción.

## Prerrequisitos

- XAMPP con MySQL/MariaDB corriendo (puerto 3306)
- Python 3.10+
- Git

## Instalación

### 1. Clonar el repositorio

```bash
git clone git@github.com:antoniodavila/stocks.git
cd stocks
```

### 2. Configurar variables de entorno

```bash
cp .env.example .env
# Editar .env con tus credenciales
```

### 3. Crear virtualenv e instalar dependencias Python

```bash
cd scripts
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 4. Crear la base de datos

```bash
mysql -u root < db/schema.sql
```

### 5. Verificar conexión

```bash
cd scripts
source venv/bin/activate
python config.py
```

## Estructura del proyecto

```
stocks/
├── db/              # Schema SQL y migraciones
├── scripts/         # Scripts Python (data loaders, analyzers)
├── dashboard/       # Frontend PHP + jQuery + Chart.js
├── lambdas/         # AWS Lambda (Milestone 4)
├── .env             # Variables de entorno (no commitear)
└── README.md
```

## Scripts Python

Cada script se ejecuta como CLI independiente:

```bash
cd scripts
source venv/bin/activate
python data_loaders/load_prices.py --help
python data_loaders/load_fundamentals.py --help
python analyzers/seasonality_calc.py --help
```

## Dashboard

Acceder via XAMPP: `http://localhost/stocks/dashboard/`
