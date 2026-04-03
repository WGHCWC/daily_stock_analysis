# -*- coding: utf-8 -*-
"""
===================================
API 依赖注入模块
===================================

职责：
1. 提供数据库 Session 依赖
2. 提供配置依赖
3. 提供服务层依赖
"""

from typing import Generator

from fastapi import Request
from sqlalchemy.orm import Session

from src.storage import DatabaseManager
from src.config import get_config, Config
from src.services.operation_log_service import OperationLogService
from src.services.system_config_service import SystemConfigService
from src.services.watchlist_service import WatchlistService


def get_db() -> Generator[Session, None, None]:
    """
    获取数据库 Session 依赖
    
    使用 FastAPI 依赖注入机制，确保请求结束后自动关闭 Session
    
    Yields:
        Session: SQLAlchemy Session 对象
        
    Example:
        @router.get("/items")
        async def get_items(db: Session = Depends(get_db)):
            ...
    """
    db_manager = DatabaseManager.get_instance()
    session = db_manager.get_session()
    try:
        yield session
    finally:
        session.close()


def get_config_dep() -> Config:
    """
    获取配置依赖
    
    Returns:
        Config: 配置单例对象
    """
    return get_config()


def get_database_manager() -> DatabaseManager:
    """
    获取数据库管理器依赖
    
    Returns:
        DatabaseManager: 数据库管理器单例对象
    """
    return DatabaseManager.get_instance()


def get_system_config_service(request: Request) -> SystemConfigService:
    """Get app-lifecycle shared SystemConfigService instance."""
    service = getattr(request.app.state, "system_config_service", None)
    if service is None:
        service = SystemConfigService()
        request.app.state.system_config_service = service
    return service


def get_watchlist_service(request: Request) -> WatchlistService:
    """Get app-lifecycle shared WatchlistService instance."""
    service = getattr(request.app.state, "watchlist_service", None)
    if service is None:
        service = WatchlistService()
        request.app.state.watchlist_service = service
    return service


def get_operation_log_service(request: Request) -> OperationLogService:
    """Get app-lifecycle shared OperationLogService instance."""
    service = getattr(request.app.state, "operation_log_service", None)
    if service is None:
        service = OperationLogService()
        request.app.state.operation_log_service = service
    return service
