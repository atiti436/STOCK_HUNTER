FROM python:3.11-slim

WORKDIR /app

# 設定時區為台灣（Asia/Taipei）
ENV TZ=Asia/Taipei
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# 複製依賴檔案
COPY requirements_v2.txt .

# 安裝依賴
RUN pip install --no-cache-dir -r requirements_v2.txt

# 複製所有檔案
COPY . .

# 暴露端口
EXPOSE 8080

# 啟動應用
CMD ["python", "-u", "stock_hunter_v3.py"]
