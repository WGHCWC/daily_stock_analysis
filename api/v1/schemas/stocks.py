# -*- coding: utf-8 -*-
"""
===================================
股票数据相关模型
===================================

职责：
1. 定义股票实时行情模型
2. 定义历史 K 线数据模型
"""

from typing import Optional, List

from pydantic import BaseModel, Field


class StockQuote(BaseModel):
    """股票实时行情"""
    
    stock_code: str = Field(..., description="股票代码")
    stock_name: Optional[str] = Field(None, description="股票名称")
    current_price: float = Field(..., description="当前价格")
    change: Optional[float] = Field(None, description="涨跌额")
    change_percent: Optional[float] = Field(None, description="涨跌幅 (%)")
    open: Optional[float] = Field(None, description="开盘价")
    high: Optional[float] = Field(None, description="最高价")
    low: Optional[float] = Field(None, description="最低价")
    prev_close: Optional[float] = Field(None, description="昨收价")
    volume: Optional[float] = Field(None, description="成交量（股）")
    amount: Optional[float] = Field(None, description="成交额（元）")
    update_time: Optional[str] = Field(None, description="更新时间")
    
    class Config:
        json_schema_extra = {
            "example": {
                "stock_code": "600519",
                "stock_name": "贵州茅台",
                "current_price": 1800.00,
                "change": 15.00,
                "change_percent": 0.84,
                "open": 1785.00,
                "high": 1810.00,
                "low": 1780.00,
                "prev_close": 1785.00,
                "volume": 10000000,
                "amount": 18000000000,
                "update_time": "2024-01-01T15:00:00"
            }
        }


class KLineData(BaseModel):
    """K 线数据点"""
    
    date: str = Field(..., description="日期")
    open: float = Field(..., description="开盘价")
    high: float = Field(..., description="最高价")
    low: float = Field(..., description="最低价")
    close: float = Field(..., description="收盘价")
    volume: Optional[float] = Field(None, description="成交量")
    amount: Optional[float] = Field(None, description="成交额")
    change_percent: Optional[float] = Field(None, description="涨跌幅 (%)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "date": "2024-01-01",
                "open": 1785.00,
                "high": 1810.00,
                "low": 1780.00,
                "close": 1800.00,
                "volume": 10000000,
                "amount": 18000000000,
                "change_percent": 0.84
            }
        }


class ExtractItem(BaseModel):
    """单条提取结果（代码、名称、置信度）"""

    code: Optional[str] = Field(None, description="股票代码，None 表示解析失败")
    name: Optional[str] = Field(None, description="股票名称（如有）")
    confidence: str = Field("medium", description="置信度：high/medium/low")


class ExtractFromImageResponse(BaseModel):
    """图片股票代码提取响应"""

    codes: List[str] = Field(..., description="提取的股票代码（已去重，向后兼容）")
    items: List[ExtractItem] = Field(default_factory=list, description="提取结果明细（代码+名称+置信度）")
    raw_text: Optional[str] = Field(None, description="原始 LLM 响应（调试用）")


class StockHistoryResponse(BaseModel):
    """股票历史行情响应"""
    
    stock_code: str = Field(..., description="股票代码")
    stock_name: Optional[str] = Field(None, description="股票名称")
    period: str = Field(..., description="K 线周期")
    data: List[KLineData] = Field(default_factory=list, description="K 线数据列表")
    
    class Config:
        json_schema_extra = {
            "example": {
                "stock_code": "600519",
                "stock_name": "贵州茅台",
                "period": "daily",
                "data": []
            }
        }


class WatchlistStockItem(BaseModel):
    """自选股管理页条目。"""

    code: str = Field(..., description="股票代码")
    name: str = Field(..., description="股票名称")
    added_at: Optional[str] = Field(None, description="添加时间")
    added_price: Optional[float] = Field(None, description="添加时价格")
    current_price: Optional[float] = Field(None, description="当前价格")
    gain_percent: Optional[float] = Field(None, description="添加后涨跌幅 (%)")
    updated_at: Optional[str] = Field(None, description="最近行情刷新时间")


class WatchlistResponse(BaseModel):
    """自选股列表响应。"""

    items: List[WatchlistStockItem] = Field(default_factory=list, description="自选股列表")


class WatchlistAddRequest(BaseModel):
    """新增自选股请求。"""

    code: str = Field(..., min_length=1, description="股票代码")
    name: Optional[str] = Field(None, description="股票名称（可选）")


class WatchlistAddResponse(BaseModel):
    """新增自选股响应。"""

    success: bool = Field(True, description="是否添加成功")
    item: WatchlistStockItem = Field(..., description="新增后的自选股条目")


class WatchlistBatchAddRequest(BaseModel):
    """批量新增自选股请求。"""

    codes: List[str] = Field(..., min_length=1, description="股票代码列表")
    name: Optional[str] = Field(None, description="股票名称，仅单只股票时生效")


class WatchlistBatchAddResultItem(BaseModel):
    """批量新增任务中的单条结果。"""

    code: str = Field(..., description="股票代码")
    status: str = Field(..., description="处理状态：success / error")
    message: str = Field(..., description="处理结果说明")
    item: Optional[WatchlistStockItem] = Field(None, description="成功新增后的自选股条目")


class WatchlistBatchTaskResponse(BaseModel):
    """批量新增任务状态响应。"""

    task_id: str = Field(..., description="任务 ID")
    status: str = Field(..., description="任务状态：running / cancelling / cancelled / completed / failed")
    total: int = Field(..., ge=0, description="总任务数")
    completed: int = Field(..., ge=0, description="已处理数量")
    results: List[WatchlistBatchAddResultItem] = Field(default_factory=list, description="逐条处理结果")
    error_message: Optional[str] = Field(None, description="任务级错误信息")
    created_at: Optional[str] = Field(None, description="任务创建时间")
    updated_at: Optional[str] = Field(None, description="任务更新时间")
    finished_at: Optional[str] = Field(None, description="任务结束时间")


class WatchlistDeleteResponse(BaseModel):
    """删除自选股响应。"""

    success: bool = Field(True, description="是否删除成功")
    code: str = Field(..., description="已删除的股票代码")
