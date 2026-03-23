import os
import json
import requests
from datetime import datetime
from playwright.async_api import async_playwright
import asyncio
import sys
import urllib.parse

async def get_rank(item_manage_id, keyword):
    """楽天で商品の検索順位を取得"""
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        
        try:
            # 楽天検索ページにアクセス
            search_url = f"https://search.rakuten.co.jp/search/mall/{keyword}/"
            print(f"[DEBUG] Accessing URL: {search_url}")
            await page.goto(search_url, wait_until="networkidle", timeout=30000)
            
            # 商品要素を取得（PR商品を除外）
            products = await page.query_selector_all(
                'a[href*="item.rakuten.co.jp"][href*="' + item_manage_id + '"]'
            )
            
            if products:
                print(f"[DEBUG] Found {len(products)} matching products")
                # 最初にマッチした商品の順位を計算
                all_items = await page.query_selector_all(
                    'a[href*="item.rakuten.co.jp"]'
                )
                print(f"[DEBUG] Total items on page: {len(all_items)}")
                
                for idx, item in enumerate(all_items, 1):
                    href = await item.get_attribute("href")
                    if item_manage_id in href:
                        print(f"[DEBUG] Found item at position {idx}")
                        await browser.close()
                        return {
                            "rank": idx,
                            "page": 1,
                            "status": "found"
                        }
            
            print(f"[DEBUG] Item not found in search results")
            await browser.close()
            return {
                "rank": None,
                "page": None,
                "status": "not_found"
            }
        except Exception as e:
            print(f"[ERROR] Exception occurred: {str(e)}", file=sys.stderr)
            await browser.close()
            return {
                "rank": None,
                "page": None,
                "status": "error"
            }

async def main():
    dashboard_url = os.getenv("DASHBOARD_URL")
    user_id = os.getenv("USER_ID")
    
    print(f"[INFO] Starting rank checker")
    print(f"[INFO] DASHBOARD_URL: {dashboard_url}")
    print(f"[INFO] USER_ID: {user_id}")
    
    if not dashboard_url or not user_id:
        print("[ERROR] DASHBOARD_URL and USER_ID environment variables are required", file=sys.stderr)
        return
    
    try:
        user_id = int(user_id)
    except ValueError:
        print("[ERROR] USER_ID must be a number", file=sys.stderr)
        return
    
    # ダッシュボードから設定を取得
    try:
        # tRPC の正しい形式でリクエストを送信
        # GET /api/trpc/rankData.getConfigs?input={"userId":1}
        input_data = json.dumps({"userId": user_id})
        config_url = f"{dashboard_url}/api/trpc/rankData.getConfigs?input={urllib.parse.quote(input_data)}"
        print(f"[DEBUG] Fetching configs from: {config_url}")
        
        response = requests.get(config_url, timeout=10)
        print(f"[DEBUG] Response status: {response.status_code}")
        print(f"[DEBUG] Response headers: {dict(response.headers)}")
        print(f"[DEBUG] Response body: {response.text[:500]}")
        
        response.raise_for_status()
        result = response.json()
        
        print(f"[DEBUG] Config response: {json.dumps(result, indent=2)}")
        
        # tRPC のレスポンス形式に対応
        configs = result.get("result", {}).get("data", [])
        print(f"[INFO] Found {len(configs)} configurations")
    except requests.exceptions.HTTPError as e:
        print(f"[ERROR] HTTP Error: {e.response.status_code} - {e.response.text[:500]}", file=sys.stderr)
        return
    except Exception as e:
        print(f"[ERROR] Failed to fetch configs: {str(e)}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return
    
    if not configs:
        print("[WARNING] No configurations found", file=sys.stderr)
        return
    
    # 各設定について順位を取得
    for config in configs:
        if config.get("isActive") != 1:
            print(f"[INFO] Skipping inactive config: {config['itemManageId']}")
            continue
        
        print(f"[INFO] Checking: {config['itemManageId']} - {config['keyword']}")
        result = await get_rank(config["itemManageId"], config["keyword"])
        print(f"[DEBUG] Rank check result: {result}")
        
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
            
            send_url = f"{dashboard_url}/api/trpc/rankData.receive"
            print(f"[DEBUG] Sending result to: {send_url}")
            print(f"[DEBUG] Payload: {json.dumps(payload, indent=2)}")
            
            response = requests.post(send_url, json=payload, timeout=10)
            print(f"[DEBUG] Send response status: {response.status_code}")
            print(f"[DEBUG] Send response body: {response.text[:500]}")
            
            response.raise_for_status()
            
            print(f"[INFO] Successfully sent result: {result['status']}")
        except requests.exceptions.HTTPError as e:
            print(f"[ERROR] HTTP Error sending result: {e.response.status_code} - {e.response.text[:500]}", file=sys.stderr)
        except Exception as e:
            print(f"[ERROR] Failed to send result: {str(e)}", file=sys.stderr)
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
