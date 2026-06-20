import os
from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    Float,
    String,
    Boolean,
    ForeignKey,
    Index,
)
from sqlalchemy.orm import declarative_base, sessionmaker

Base = declarative_base()

class Candle(Base):
    __tablename__ = 'candles'
    
    time = Column(Integer, primary_key=True)
    symbol = Column(String(20), primary_key=True)
    interval = Column(String(10), primary_key=True)
    open = Column(Float, nullable=False)
    high = Column(Float, nullable=False)
    low = Column(Float, nullable=False)
    close = Column(Float, nullable=False)
    volume = Column(Float, nullable=False)
    macd = Column(Float)
    macd_signal = Column(Float)
    macd_hist = Column(Float)
    k = Column(Float)
    d = Column(Float)
    j = Column(Float)
    atr_14 = Column(Float)
    atr_200 = Column(Float)

    __table_args__ = (
        Index('idx_candles_sym_int_time', 'symbol', 'interval', 'time'),
    )


class OrderBlock(Base):
    __tablename__ = 'order_blocks'
    
    ob_id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(20), nullable=False)
    interval = Column(String(10), nullable=False)
    type = Column(String(10), nullable=False)  # 'DEMAND' or 'SUPPLY'
    top = Column(Float, nullable=False)
    bottom = Column(Float, nullable=False)
    created_at = Column(Integer, nullable=False)  # bar index
    ob_bar = Column(Integer, nullable=False)      # bar index
    level = Column(String(10), nullable=False)     # 'internal' or 'swing'
    structure = Column(String(10), nullable=False) # 'CHoCH' or 'BOS'
    mitigated_at = Column(Integer)                 # bar index or Null
    quality = Column(Integer, nullable=False)      # composite 0-5
    quality_displacement = Column(Boolean, nullable=False)
    quality_large_bar = Column(Boolean, nullable=False)
    quality_fvg = Column(Boolean, nullable=False)
    quality_liquidity_sweep = Column(Boolean, nullable=False)
    quality_volume_expansion = Column(Boolean, nullable=False)

    __table_args__ = (
        Index('idx_obs_sym_int', 'symbol', 'interval'),
        Index('idx_obs_created', 'created_at'),
    )


class OBTouch(Base):
    __tablename__ = 'ob_touches'
    
    touch_id = Column(Integer, primary_key=True, autoincrement=True)
    ob_id = Column(Integer, ForeignKey('order_blocks.ob_id'), nullable=False)
    time = Column(Integer, nullable=False)  # bar index / timestamp
    touch_price = Column(Float, nullable=False)
    macd = Column(Float)
    macd_signal = Column(Float)
    macd_hist = Column(Float)
    k = Column(Float)
    d = Column(Float)
    j = Column(Float)
    k_accel = Column(Float)
    atr_14 = Column(Float)
    atr_200 = Column(Float)

    __table_args__ = (
        Index('idx_touches_ob_id', 'ob_id'),
        Index('idx_touches_time', 'time'),
    )


class Trade(Base):
    __tablename__ = 'trades'
    
    trade_id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(20), nullable=False)
    interval = Column(String(10), nullable=False)
    side = Column(String(10), nullable=False)  # 'LONG' or 'SHORT'
    min_ob_quality = Column(Integer, nullable=False)  # quality threshold used
    entry_time = Column(Integer, nullable=False)  # bar index / timestamp
    exit_time = Column(Integer, nullable=False)   # bar index / timestamp
    entry_price = Column(Float, nullable=False)
    exit_price = Column(Float, nullable=False)
    stop_loss = Column(Float, nullable=False)
    take_profit = Column(Float, nullable=False)
    pnl_pct = Column(Float, nullable=False)
    hold_bars = Column(Integer, nullable=False)
    exit_reason = Column(String(50), nullable=False)
    entry_ob_id = Column(Integer, ForeignKey('order_blocks.ob_id'), nullable=False)
    tp_ob_id = Column(Integer, ForeignKey('order_blocks.ob_id'), nullable=True)

    __table_args__ = (
        Index('idx_trades_sym_int', 'symbol', 'interval'),
        Index('idx_trades_entry_time', 'entry_time'),
    )


# ─── DATABASE INITIALIZATION ────────────────────────────────────────────────
def get_db_url():
    """Retrieve database URL from environment variable or fallback to SQLite."""
    return os.getenv("DATABASE_URL", "sqlite:///backtest_results.db")


def init_db(db_url=None):
    """Create tables if they don't exist."""
    if db_url is None:
        db_url = get_db_url()
    
    engine = create_engine(db_url, echo=False)
    Base.metadata.create_all(engine)
    return engine


def get_session(engine):
    """Retrieve a new session handler."""
    Session = sessionmaker(bind=engine)
    return Session()


def clear_db(engine):
    """Drop and recreate all tables."""
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
