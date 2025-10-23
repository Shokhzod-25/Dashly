col_map_candidates = {
    "date": ["date", "order_date", "dt"],
    "sku": ["sku", "product_sku", "article"],
    "title": ["title", "product_name", "name"],
    "qty": ["qty", "quantity", "count", "amount"],
    "price": ["price", "unit_price"],
    "revenue": ["revenue", "total", "sum"],
    "commission_pct": ["commission_pct", "commission", "commission_rate"],
    "platform": ["platform", "marketplace", "source"],  # NEW
}

platform = {
    "WB": "Wildberries",
    "wb": "Wildberries",
    "wildberries": "Wildberries",
    "Ozon": "Ozon",
    "ozon": "Ozon",
    "OZON": "Ozon",
}
