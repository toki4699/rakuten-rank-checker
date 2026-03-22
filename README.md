# 楽天検索順位自動計測スクリプト

このリポジトリは、楽天市場の商品検索順位を毎日自動計測し、ダッシュボードに送信するスクリプトです。

## セットアップ

### 1. GitHub Secrets の設定

リポジトリの Settings → Secrets and variables → Actions で以下の2つのシークレットを設定してください:

- `DASHBOARD_URL`: ダッシュボードの URL（例: `https://xxx.manus.space`）
- `USER_ID`: ダッシュボードのユーザーID（例: `1`）

### 2. 自動実行

GitHub Actions により、毎日 9:00 UTC (日本時間 18:00) に自動で実行されます。

### 3. 手動実行

リポジトリの Actions タブで「Check Rakuten Rank」ワークフローを選択し、「Run workflow」をクリックすることで手動実行できます。

## ファイル構成

- `.github/workflows/check-rank.yml`: GitHub Actions ワークフロー設定
- `check_rank.py`: 計測スクリプト

## ログ確認

Actions タブでワークフロー実行ログを確認できます。

## トラブルシューティング

- **Secrets が設定されていない**: Settings → Secrets and variables → Actions で設定してください
- **スクリプトがエラーで終了**: Actions のログを確認してください
- **ダッシュボードに結果が送信されない**: ダッシュボード URL が正しいか確認してください
