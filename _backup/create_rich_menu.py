import os
import sys
from linebot import LineBotApi
from linebot.models import RichMenu, RichMenuSize, RichMenuArea, RichMenuBounds, MessageAction

# ==================== 設定 ====================
LINE_CHANNEL_ACCESS_TOKEN = os.getenv('LINE_CHANNEL_ACCESS_TOKEN')

if not LINE_CHANNEL_ACCESS_TOKEN:
    print("❌ 請設定 LINE_CHANNEL_ACCESS_TOKEN 環境變數")
    sys.exit(1)

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)

def create_rich_menu():
    # 1. 定義選單結構
    rich_menu_to_create = RichMenu(
        size=RichMenuSize(width=2500, height=1686),
        selected=True,
        name="Stock Hunter Menu",
        chat_bar_text="開啟選單",
        areas=[
            # 上排左：今日分析
            RichMenuArea(
                bounds=RichMenuBounds(x=0, y=0, width=833, height=843),
                action=MessageAction(label="今日分析", text="今日分析")
            ),
            # 上排中：當沖觀察
            RichMenuArea(
                bounds=RichMenuBounds(x=833, y=0, width=833, height=843),
                action=MessageAction(label="當沖觀察", text="當沖觀察")
            ),
            # 上排右：使用說明
            RichMenuArea(
                bounds=RichMenuBounds(x=1666, y=0, width=833, height=843),
                action=MessageAction(label="使用說明", text="幫助")
            ),
            # 下排左：設定 (暫無功能)
            RichMenuArea(
                bounds=RichMenuBounds(x=0, y=843, width=833, height=843),
                action=MessageAction(label="設定", text="設定")
            ),
            # 下排中：歷史紀錄 (暫無功能)
            RichMenuArea(
                bounds=RichMenuBounds(x=833, y=843, width=833, height=843),
                action=MessageAction(label="歷史紀錄", text="歷史紀錄")
            ),
            # 下排右：聯絡作者 (暫無功能)
            RichMenuArea(
                bounds=RichMenuBounds(x=1666, y=843, width=833, height=843),
                action=MessageAction(label="聯絡作者", text="聯絡作者")
            )
        ]
    )

    # 2. 建立選單 ID
    rich_menu_id = line_bot_api.create_rich_menu(rich_menu=rich_menu_to_create)
    print(f"✅ 選單建立成功，ID: {rich_menu_id}")

    # 3. 上傳圖片
    image_path = 'rich_menu.jpg'
    if not os.path.exists(image_path):
        print(f"⚠️ 找不到圖片 {image_path}，請先準備一張 2500x1686 的圖片")
        return

    with open(image_path, 'rb') as f:
        line_bot_api.set_rich_menu_image(rich_menu_id, "image/jpeg", f)
    print("✅ 圖片上傳成功")

    # 4. 設為預設選單
    line_bot_api.set_default_rich_menu(rich_menu_id)
    print("✅ 已設為預設選單")

if __name__ == "__main__":
    create_rich_menu()
