#!/bin/bash
# 占い副業 Web アプリ 起動スクリプト

cd "$(dirname "$0")"

# .env ファイルがあれば読み込む
if [ -f .env ]; then
  export $(grep -v '^#' .env | xargs)
fi

# 依存ライブラリのインストール（初回のみ）
pip install -q -r requirements_web.txt

echo ""
echo "✨ 星詠み Web アプリ 起動中..."
echo "   http://localhost:5000"
echo ""

python3 app.py
