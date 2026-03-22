import os
import json
import requests
from datetime import datetime
from playwright.async_api import async_playwright
import asyncio

async def get_rank(item_manage_id, keyword):
    """楽天で商品の検索順位を取得"""
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        
        try:
            # 楽天検索ページにアクセス
            search_url = f"https://search.rakuten.co.jp/search/mall/{keyword}/"
            await page.goto(search_url, wait_until="networkidle")
            
            # 商品要素を取得（PR商品を除外）
            products = await page.query_selector_all(
                'a[href*="item.rakuten.co.jp"][href*="' + item_manage_id + '"]'
            )
            
            if products:
                # 最初にマッチした商品の順位を計算
                all_items = await page.query_selector_all(
                    'a[href*="item.rakuten.co.jp"]'
                )
                for idx, item in enumerate(all_items, 1):
                    href = await item.get_attribute("href")
                    if item_manage_id in href:
                        await browser.close()
                        return {
                            "rank": idx,
                            "page": 1,
                            "status": "found"
                        }
            
            await browser.close()
            return {
                "rank": None,
                "page": None,
                "status": "not_found"
            }
        except Exception as e:
            print(f"Error: {e}")
            await browser.close()
            return {
                "rank": None,
                "page": None,
                "status": "error"
            }

async def main():
    dashboard_url = os.getenv("DASHBOARD_URL")
    user_id = os.getenv("USER_ID")
    
    if not dashboard_url or not user_id:
        print("Error: DASHBOARD_URL and USER_ID environment variables are required")
        return
    
    try:
        user_id = int(user_id)
    except ValueError:
        print("Error: USER_ID must be a number")
        return
    
    # ダッシュボードから設定を取得
    try:
        response = requests.get(
            f"{dashboard_url}/api/trpc/rankData.getConfigs?input=" + json.dumps({"userId": user_id}),
            timeout=10
        )
        response.raise_for_status()
        result = response.json()
        configs = result.get("result", {}).get("data", [])
        print(f"Found {len(configs)} configurations")
    except Exception as e:
        print(f"Failed to fetch configs: {e}")
        return
    
    if not configs:
        print("No configurations found")
        return
    
    # 各設定について順位を取得
    for config in configs:
        if config.get("isActive") != 1:
            print(f"Skipping inactive config: {config['itemManageId']}")
            continue
        
        print(f"Checking: {config['itemManageId']} - {config['keyword']}")
        result = await get_rank(config["itemManageId"], config["keyword"])
        
        # 結果をダッシュボードに送信
        try:
            payload = {
                "itemManageId": config["itemManageId"],
                "keyword": config["keyword"],
                "rank": result.get("rank"),
                "page": result.get("page"),
                "status": result["status"],
                "measuredAt": datetime.utcnow().isoformat() + "Z",
                "userId": user_id
            }
            
            response = requests.post(
                f"{dashboard_url}/api/trpc/rankData.receive",
                json=payload,
                timeout=10
            )
            response.raise_for_status()
            print(f"  Result: {result['status']}")
        except Exception as e:
            print(f"  Failed to send result: {e}")

if __name__ == "__main__":
    asyncio.run(main())
