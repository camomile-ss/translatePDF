# translatePDF
PDFを日本語に翻訳

## 使い方(1)

translatePDFjp.exe に、入力ファイルをドラッグ＆ドロップ

## 使い方(2)
コマンドプロンプトから

`translatePDFjp.exe xxx.pdf`

  * xxx.pdf : 入力ファイル。テキストファイルも可。
  * オプション
    * -h, --help            : show this help message and exit
    * -o OUTDIR, --outdir OUTDIR : 出力ディレクトリ。 省略した場合は入力ファイルと同じ場所に出力されます。
    * -f, --formatted       : 整形済み。 余分な改行の削除などの整形が終わっているテキストファイルを入力する場合指定してください。
    * -t TRYTIMES, --trytimes TRYTIMES : 翻訳が返答しない場合にリトライする回数。default 1。
    * -s TRYSPAN, --tryspan TRYSPAN : 翻訳が返答しない場合にリトライする間隔(秒)。default 1。

## 出力ファイル

### xxx_parse_pdf.txt
pdfから取り出したテキスト。
入力がテキストファイルのときは作成しません。

### xxx_original.txt
整形したテキスト。
オプション -f, --formatted 指定のときは作成しません。

### xxx_japanese.txt
日本語翻訳文。

## proxy
環境変数を読みます。不足は >> で入力を促します。
