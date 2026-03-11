CREATE DATABASE IF NOT EXISTS seasonal_stocks
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE seasonal_stocks;

-- 1. CATÁLOGO
CREATE TABLE IF NOT EXISTS tickers (
    id INT AUTO_INCREMENT PRIMARY KEY,
    ticker VARCHAR(10) NOT NULL UNIQUE,
    name VARCHAR(100),
    sector VARCHAR(50),
    industry VARCHAR(100),
    market_cap BIGINT,
    sp500 BOOLEAN DEFAULT TRUE,
    active BOOLEAN DEFAULT TRUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_sector (sector),
    INDEX idx_sp500 (sp500)
) ENGINE=InnoDB;

-- 2. PRECIOS
CREATE TABLE IF NOT EXISTS stock_prices (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    ticker VARCHAR(10) NOT NULL,
    date DATE NOT NULL,
    open DECIMAL(12,4),
    high DECIMAL(12,4),
    low DECIMAL(12,4),
    close DECIMAL(12,4),
    adj_close DECIMAL(12,4),
    volume BIGINT,
    UNIQUE KEY uk_ticker_date (ticker, date),
    INDEX idx_ticker (ticker),
    INDEX idx_date (date),
    FOREIGN KEY (ticker) REFERENCES tickers(ticker) ON DELETE CASCADE
) ENGINE=InnoDB;

-- 3. RETORNOS MENSUALES
CREATE TABLE IF NOT EXISTS monthly_returns (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    ticker VARCHAR(10) NOT NULL,
    year SMALLINT NOT NULL,
    month TINYINT NOT NULL,
    return_pct DECIMAL(8,4),
    adj_close_start DECIMAL(12,4),
    adj_close_end DECIMAL(12,4),
    UNIQUE KEY uk_ticker_year_month (ticker, year, month),
    FOREIGN KEY (ticker) REFERENCES tickers(ticker) ON DELETE CASCADE
) ENGINE=InnoDB;

-- 4. FUNDAMENTALES
CREATE TABLE IF NOT EXISTS fundamentals (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    ticker VARCHAR(10) NOT NULL,
    period DATE NOT NULL,
    period_type ENUM('Q','A') NOT NULL,
    revenue BIGINT,
    net_income BIGINT,
    eps_diluted DECIMAL(8,4),
    gross_profit BIGINT,
    operating_income BIGINT,
    ebitda BIGINT,
    fcf BIGINT COMMENT 'Operating CF - CapEx',
    operating_cf BIGINT,
    capex BIGINT,
    shares_diluted BIGINT,
    source VARCHAR(20) COMMENT 'edgar|fmp|alpha_vantage',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_ticker_period (ticker, period, period_type),
    FOREIGN KEY (ticker) REFERENCES tickers(ticker) ON DELETE CASCADE
) ENGINE=InnoDB;

-- 5. BALANCE SHEET
CREATE TABLE IF NOT EXISTS balance_sheet (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    ticker VARCHAR(10) NOT NULL,
    period DATE NOT NULL,
    total_assets BIGINT,
    total_equity BIGINT,
    total_debt BIGINT,
    long_term_debt BIGINT,
    short_term_debt BIGINT,
    current_assets BIGINT,
    current_liabilities BIGINT,
    cash_and_equivalents BIGINT,
    retained_earnings BIGINT,
    source VARCHAR(20),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_ticker_period (ticker, period),
    FOREIGN KEY (ticker) REFERENCES tickers(ticker) ON DELETE CASCADE
) ENGINE=InnoDB;

-- 6. RATIOS DE PRECIO
CREATE TABLE IF NOT EXISTS price_ratios (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    ticker VARCHAR(10) NOT NULL,
    date DATE NOT NULL,
    pe_ratio DECIMAL(10,4),
    pb_ratio DECIMAL(10,4),
    pfcf_ratio DECIMAL(10,4),
    ev_ebitda DECIMAL(10,4),
    market_cap BIGINT,
    enterprise_value BIGINT,
    UNIQUE KEY uk_ticker_date (ticker, date),
    FOREIGN KEY (ticker) REFERENCES tickers(ticker) ON DELETE CASCADE
) ENGINE=InnoDB;

-- 7. RATIOS DE CALIDAD
CREATE TABLE IF NOT EXISTS quality_ratios (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    ticker VARCHAR(10) NOT NULL,
    period DATE NOT NULL,
    roe DECIMAL(8,4) COMMENT 'Net Income / Avg Equity',
    roic DECIMAL(8,4) COMMENT 'NOPAT / Invested Capital',
    gross_margin DECIMAL(8,4) COMMENT 'Gross Profit / Revenue',
    operating_margin DECIMAL(8,4),
    net_margin DECIMAL(8,4),
    debt_equity DECIMAL(8,4),
    current_ratio DECIMAL(8,4),
    interest_coverage DECIMAL(8,4),
    asset_turnover DECIMAL(8,4),
    UNIQUE KEY uk_ticker_period (ticker, period),
    FOREIGN KEY (ticker) REFERENCES tickers(ticker) ON DELETE CASCADE
) ENGINE=InnoDB;

-- 8. SCORING
CREATE TABLE IF NOT EXISTS value_scores (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    ticker VARCHAR(10) NOT NULL,
    calculated_at DATE NOT NULL,
    total_score DECIMAL(5,2) COMMENT '0-100',
    quality_score DECIMAL(5,2),
    valuation_score DECIMAL(5,2),
    solidity_score DECIMAL(5,2),
    growth_score DECIMAL(5,2),
    sector_percentile DECIMAL(5,2) COMMENT 'Percentil dentro de su sector',
    quality_trend TINYINT COMMENT '-1=deteriorating, 0=stable, 1=improving',
    UNIQUE KEY uk_ticker_date (ticker, calculated_at),
    FOREIGN KEY (ticker) REFERENCES tickers(ticker) ON DELETE CASCADE
) ENGINE=InnoDB;

-- 9. ESTACIONALIDAD
CREATE TABLE IF NOT EXISTS seasonality_stats (
    id INT AUTO_INCREMENT PRIMARY KEY,
    ticker VARCHAR(10) NOT NULL,
    month TINYINT NOT NULL COMMENT '1-12',
    avg_return DECIMAL(8,4),
    win_rate DECIMAL(5,2) COMMENT 'Porcentaje 0-100',
    best_return DECIMAL(8,4),
    worst_return DECIMAL(8,4),
    years_analyzed TINYINT,
    last_updated DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_ticker_month (ticker, month),
    FOREIGN KEY (ticker) REFERENCES tickers(ticker) ON DELETE CASCADE
) ENGINE=InnoDB;

-- 10. ESTRATEGIAS
CREATE TABLE IF NOT EXISTS strategies (
    id INT AUTO_INCREMENT PRIMARY KEY,
    ticker VARCHAR(10) NOT NULL,
    entry_month TINYINT NOT NULL,
    entry_day_type ENUM('first','last') NOT NULL DEFAULT 'first',
    exit_month TINYINT NOT NULL,
    exit_day_type ENUM('first','last') NOT NULL DEFAULT 'last',
    initial_capital DECIMAL(12,2) NOT NULL,
    year_start SMALLINT NOT NULL,
    year_end SMALLINT NOT NULL,
    name VARCHAR(100),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- 11. RESULTADOS BACKTEST
CREATE TABLE IF NOT EXISTS backtest_results (
    id INT AUTO_INCREMENT PRIMARY KEY,
    strategy_id INT NOT NULL,
    total_return DECIMAL(8,4),
    cagr DECIMAL(8,4),
    win_rate DECIMAL(5,2),
    avg_cycle_return DECIMAL(8,4),
    best_year_return DECIMAL(8,4),
    worst_year_return DECIMAL(8,4),
    max_drawdown DECIMAL(8,4),
    sharpe_ratio DECIMAL(8,4),
    total_cycles INT,
    winning_cycles INT,
    calculated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (strategy_id) REFERENCES strategies(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- 12. CICLOS BACKTEST
CREATE TABLE IF NOT EXISTS backtest_cycles (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    strategy_id INT NOT NULL,
    year SMALLINT NOT NULL,
    entry_date DATE,
    exit_date DATE,
    entry_price DECIMAL(12,4),
    exit_price DECIMAL(12,4),
    return_pct DECIMAL(8,4),
    capital_start DECIMAL(12,2),
    capital_end DECIMAL(12,2),
    buyhold_return DECIMAL(8,4) COMMENT 'Buy and hold mismo periodo',
    FOREIGN KEY (strategy_id) REFERENCES strategies(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- 13. NARRATIVAS IA
CREATE TABLE IF NOT EXISTS ai_narratives (
    id INT AUTO_INCREMENT PRIMARY KEY,
    ticker VARCHAR(10) NOT NULL,
    generated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    narrative LONGTEXT,
    model_version VARCHAR(50),
    expires_at DATETIME COMMENT 'Cacheo 30 dias',
    prompt_tokens INT,
    completion_tokens INT,
    FOREIGN KEY (ticker) REFERENCES tickers(ticker) ON DELETE CASCADE
) ENGINE=InnoDB;
