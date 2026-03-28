#!/usr/bin/env python3
import os
import json
import requests
from datetime import datetime
from playwright.async_api import async_playwright
import asyncio
import sys
import time

async def get_rank(item_manage_id, keyword):
    """楽天で商品の検索順位を取得（1ページ目のみ）"""
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-first-run',
                '--no-default-browser-check'
            ]
        )
        
        # より自然な User-Agent を設定
        user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        
        context = await browser.new_context(
            user_agent=user_agent,
            viewport={'width': 1920, 'height': 1080}
        )
        
        page = await context.new_page()
        
        try:
            # 楽天検索ページにアクセス
            search_url = f"https://search.rakuten.co.jp/search/mall/{keyword}/"
            print(f"[DEBUG] Accessing URL: {search_url}")
            
            # ページを読み込み
            await page.goto(search_url, wait_until="networkidle", timeout=60000)
            
            # JavaScript が実行されるまで待機
            await page.wait_for_timeout(3000)
            
            # ページのスクロールをシミュレート（より自然に見せる）
            await page.evaluate("window.scrollBy(0, window.innerHeight)")
            await page.wait_for_timeout(1000)
            
            # 1ページ目の商品要素を取得（最初の100件程度）
            products = await page.query_selector_all(
                'a[href*="item.rakuten.co.jp"]'
            )
            
            print(f"[DEBUG] Total items on page 1: {len(products)}")
            
            # 商品が見つからない場合、別のセレクタを試す
            if len(products) == 0:
                print(f"[DEBUG] No products found with first selector, trying alternative...")
                products = await page.query_selector_all(
                    'a[data-item-id]'
                )
                print(f"[DEBUG] Total items with alternative selector: {len(products)}")
            
            # 商品管理番号を含む商品を検索
            for idx, item in enumerate(products, 1):
                href = await item.get_attribute("href")
                if href and str(item_manage_id) in href:
                    print(f"[DEBUG] Found item at position {idx}")
                    await browser.close()
                    return {
                        "rank": idx,
                        "page": 1,
                        "status": "found"
                    }
            
            print(f"[DEBUG] Item not found in search results (page 1)")
            await browser.close()
            return {
                "rank": None,
                "page": None,
                "status": "not_found"
            }
        except asyncio.TimeoutError:
            print(f"[ERROR] Timeout while accessing {search_url}", file=sys.stderr)
            await browser.close()
            return {
                "rank": None,
                "page": None,
                "status": "timeout"
            }
        except Exception as e:
            print(f"[ERROR] Exception occurred: {str(e)}", file=sys.stderr)
            try:
                await browser.close()
            except:
                pass
            return {
                "rank": None,
                "page": None,
                "status": "error"
            }

async def main():
    dashboard_url = os.getenv("DASHBOARD_URL")
    user_id = os.getenv("USER_ID")
    
    print(f"[INFO] Starting rank checker (GAS Web App version)")
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
    
    # GAS Web アプリから設定を取得
    try:
        # GAS Web アプリの API エンドポイント
        config_url = f"{dashboard_url}?action=api&method=getConfigs&userId={user_id}"
        
        print(f"[DEBUG] Fetching configs from: {config_url}")
        
        response = requests.get(config_url, timeout=10)
        print(f"[DEBUG] Response status: {response.status_code}")
        print(f"[DEBUG] Response body: {response.text[:1000]}")
        
        response.raise_for_status()
        configs = response.json()
        
        print(f"[INFO] Found {len(configs)} configurations")
    except requests.exceptions.HTTPError as e:
        print(f"[ERROR] HTTP Error: {e.response.status_code}", file=sys.stderr)
        print(f"[ERROR] Response: {e.response.text[:1000]}", file=sys.stderr)
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
    for i, config in enumerate(configs):
        if config.get("isActive") != 1:
            print(f"[INFO] Skipping inactive config: {config['itemManageId']}")
            continue
        
        print(f"[INFO] Checking: {config['itemManageId']} - {config['keyword']}")
        result = await get_rank(config["itemManageId"], config["keyword"])
        print(f"[DEBUG] Rank check result: {result}")
        
        # 結果を GAS Web アプリに送信
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
            
            send_url = f"{dashboard_url}?action=api&method=receiveRankData"
            print(f"[DEBUG] Sending result to: {send_url}")
            print(f"[DEBUG] Payload: {json.dumps(payload, indent=2)}")
            
            response = requests.post(send_url, json=payload, timeout=10)
            print(f"[DEBUG] Send response status: {response.status_code}")
            print(f"[DEBUG] Send response body: {response.text[:500]}")
            
            response.raise_for_status()
            
            print(f"[INFO] Successfully sent result: {result['status']}")
        except requests.exceptions.HTTPError as e:
            print(f"[ERROR] HTTP Error sending result: {e.response.status_code}", file=sys.stderr)
            print(f"[ERROR] Response: {e.response.text[:500]}", file=sys.stderr)
        except Exception as e:
            print(f"[ERROR] Failed to send result: {str(e)}", file=sys.stderr)
            import traceback
            traceback.print_exc()
        
        # リクエスト間に遅延を追加（楽天への負荷を減らす）
        if i < len(configs) - 1:
            print(f"[DEBUG] Waiting 5 seconds before next request...")
            await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(main())
