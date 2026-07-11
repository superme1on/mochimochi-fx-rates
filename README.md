# もちもちFX rates

VRChatワールド「もちもちFX」用の公開JSONフィードです。

`docs/rates.json` はGitHub ActionsでFX市場の稼働時間中に約5分間隔で生成され、GitHub Pagesへ直接デプロイされます。Actionsの混雑やPagesキャッシュにより、実際の反映には数分から十数分の遅延が生じる場合があります。ECB基準値は平日に1回だけ更新し、5分処理では保存済みの基準値を使うため、データ提供元へ不要な連続アクセスを行いません。

## 価格の意味

- アンカー：European Central BankのUSD/JPY日次参考レート（Frankfurter経由）
- 障害時アンカー：CC0のfawazahmed0 currency-api
- 5分足：アンカー周辺に生成する決定論的なSIM tick
- Bid / Ask：ゲーム用の合成価格
- Spread：0.010 JPY固定
- 用途：仮想通貨「mochi」だけを使用するゲーム内シミュレーション

これは投資・決済・実取引に使用できるリアルタイム価格ではありません。JSONの `feed.mode` は `reference_anchored_sim`、`quote_kind` は `indicative_game_quote` として公開されます。`market_status` はUTC基準の簡易FX週判定であり、取引所の公式セッション状態ではありません。

## ローカル実行

```bash
python3 -m unittest discover -s tests -v
python3 scripts/update_reference.py --output data/usdjpy-reference.json
python3 scripts/update_rates.py --reference data/usdjpy-reference.json --output docs/rates.json
```

公開先：<https://superme1on.github.io/mochimochi-fx-rates/rates.json>
