# coding: utf-8
''' PDFを日本語に翻訳 '''
import sys
import argparse
import os
import re
import cchardet
import json
import time
import requests
import urllib.parse
from getpass import getpass
from googletrans import Translator

def parse_pdf_pages(pdffname):
    ''' PDFから各ページのテキスト抽出 '''

    from pdfminer.pdfinterp import PDFResourceManager, PDFPageInterpreter
    from pdfminer.converter import TextConverter
    from pdfminer.layout import LAParams
    from pdfminer.pdfpage import PDFPage
    from pdfminer.pdfdocument import PDFTextExtractionNotAllowed
    from io import StringIO

    p_txts = []
    rsrcmgr = PDFResourceManager()

    with open(pdffname, 'rb') as pdff:
        try:
            for p in PDFPage.get_pages(pdff):
                with StringIO() as strio, \
                     TextConverter(rsrcmgr, strio, codec='utf-8', laparams=LAParams()) as device:
                    interpreter = PDFPageInterpreter(rsrcmgr, device)
                    interpreter.process_page(p)
                    p_txts.append(strio.getvalue())
        except PDFTextExtractionNotAllowed:
            print('[err] PDF {0} text extraction not allowed.'.format(pdffname))
            sys.exit()
        except Exception as e:
            print('[err]: {0}'.format(type(e)))
            print('e: {0}'.format(e))
            print('e.args: {0}'.format(e.args))
            sys.exit()

    return p_txts

def parse_pdf(pdffname):
    ''' PDFテキスト抽出 '''

    pages = parse_pdf_pages(pdffname)
    # 各ページ
    for i in range(len(pages)):
        pages[i] = pages[i].strip()  # 改ページ入ってるのでstrip()
        pages[i] = re.sub(r'\n*\d*$', '\n', pages[i])  # ページを取る
        pages[i] = re.sub(r'\.\n$', '\.\n\n', pages[i])  # ピリオドで終わってたら空行入れる(わかんないけど段落終わりとみなす。)
    # つなげる
    text = ''.join(pages)
    text = '\n'.join([x.strip() for x in text.split('\n')])  # 各行strip

    return text

def read_text(txtfname):
    ''' テキストファイルを読む '''

    # 文字コード判定
    with open(txtfname, 'rb') as f:
        cd = cchardet.detect(f.read())
    with open(txtfname, 'r', encoding=cd['encoding']) as f:
        text = f.read()

    return text

def align_length(block):
    ''' blockの長さを5000文字以下に '''

    # 5000文字以下ならそのまま --------------------------------------##
    if len(block) <= 5000:
        return [block]

    # 5000文字以下に分割 --------------------------------------------##
    blocks_al = []
    num = -(-len(block) // 5000)  # 分割数
    blen = -(-len(block) // num)  # 均等に分割したときのblock長

    # ピリオド+空文字の位置のリスト
    idx_period = [im.end(0) for im in re.finditer(r'\.\s', block)]
    # 空文字の位置のリスト
    idx_space = [im.end(0) for im in re.finditer(r'\s', block)]

    b_start, b_end = 0, 0
    while b_start < len(block):
        # 残り5000文字切っていたら終わり
        if len(block) - b_end <= 5000:
            blocks_al.append(block[b_end: ])
            break

        # 均等分割長と5000の間のピリオド+空文字の位置を見つける
        idx_match = [x for x in idx_period if (x - b_start) >= blen and (x - b_start) < 5000]
        # 無いとき
        if len(idx_match) == 0:
            # 均等分割長未満で探す
            idx_match = [x for x in idx_period if (x - b_start) < blen][::-1]  # 長いほうを取るので逆に
            if len(idx_match) == 0:
                # それでもなければ空文字で分割
                idx_match = [x for x in idx_space if (x - b_start) >= blen and (x - b_start) < 5000]
                if len(idx_match) == 0:
                    idx_match = [x for x in idx_space if (x - b_start) < blen][::-1]
                    # 空文字もなければ、単純に均等分割長で分割
                    if len(idx_match) == 0:
                        idx_match = [b_start + blen]

        # block切り出し
        b_end = idx_match[0]  # 見つかった位置のリストの最初をつかう
        blocks_al.append(block[b_start: b_end].strip())
        b_start = b_end

    return blocks_al

def format_text(raw_text):
    ''' 翻訳用に整形 '''

    # 改行2行以上でblockわけ
    #blocks = raw_text.split('\n\n')
    blocks = re.split(r'\n{2,}', raw_text)
    #print(blocks)
    #sys.exit()
    # 1block5000文字以下に
    blocks_al = [x for b in blocks for x in align_length(b)]
    # 各block内の改行取る
    blocks_al = [re.sub(r'\s', ' ', b) for b in blocks_al]
    # 各blockを改行2コでつなげる
    f_text = '\n\n'.join(blocks_al) + '\n'

    return f_text

def look_env_proxy(ptns):
    ''' 環境変数あるか、名前が大文字か小文字か調べる（最初の状態） '''

    ptn1, ptn2 = ptns

    if 'https_proxy' in os.environ:
        envname = 'https_proxy'
    elif 'HTTPS_PROXY' in os.environ:
        envname = 'HTTPS_PROXY'
    else:  # 環境変数なし
        return None, None

    # パターン1
    if ptn1.search(os.environ[envname]):
        return envname, 1
    # パターン2
    elif ptn2.search(os.environ[envname]):
        return envname, 2
    else:
        return envname, -1  # 書式不正

def chk_proxy():
    '''
    proxy チェック
        proxyの環境変数チェックして必要なら設定
    '''
    ptn1 = re.compile(r'^(https?:\/\/)([^@]+:\d+)$')  # パターン1 http(s)://host:port
    ptn2 = re.compile(r'^https?:\/\/[^@]+:[^@]+@[^@]+:\d+$')  # パターン2 http(s)://user:pass@host:port
    ptns = [ptn1, ptn2]

    translator = Translator()

    first = 1
    while True:
        try:
            translator.translate('Hello world!', dest='ja')
        # proxy設定必要
        except requests.exceptions.ConnectionError:
            # 最初なら、環境変数あるか、名前が大文字か小文字か調べる
            if first:
                envname, ptn_now = look_env_proxy(ptns)
                # 環境変数なければパターン1でつくる
                if not envname:
                    envname = 'https_proxy'
                    # スキーム, host名, port番号 入力求める
                    scheme = input('proxy scheme ("https" or "http") >> ')
                    host = input('proxy host name or ip address >> ')
                    port = input('proxy port no >> ')
                    # パターン1に編集して設定
                    os.environ[envname] = '{0}://{1}:{2}'.format(scheme, host, port)
                    ptn_now = 1
                    continue  # もう一度try
                # 書式不正
                if ptn_now < 0:
                    print('[err] environ variable "{0}" invalid syntax.'.format(envname), file=sys.stderr)
                    return 9
                # 書式あってるけど通らない
                if ptn_now == 2:
                    print('[err] environ variable "{0}" not correct.'.format(envname), file=sys.stderr)
                    return 9
                first = 0

            # パターン1なら、パターン2に編集する
            if ptn_now == 1:
                mob_hp = ptn1.search(os.environ[envname])
                # ユーザ, パスワード 入力求める
                user = urllib.parse.quote(input('proxy user >> '))
                psw = urllib.parse.quote(getpass('proxy password >> '))
                # パターン2に編集して設定
                os.environ[envname] = '{0}{1}:{2}@{3}'.format(mob_hp.group(1), user, psw, mob_hp.group(2))
                ptn_now = 2
                continue  # もう一度try

            # パターン2なら、入力させたのどれか間違ってる
            if ptn_now == 2:
                print('[err] proxy input not correct.', file=sys.stderr)
                return 9
        # googleがブロック?
        except json.decoder.JSONDecodeError:
            return 0  # ここは通す
        # 他のエラー
        except Exception as e:
            print('[err]: {0}'.format(type(e)), file=sys.stderr)
            print('e.args: {0}'.format(e.args), file=sys.stderr)
            print('e: {0}'.format(e), file=sys.stderr)
            return 9
        # proxy OK
        else:
            return 0

def try_translate(text, try_span=5, try_times=5):
    ''' 日本語に翻訳 '''

    translator = Translator()

    tt = None
    cnt = 0
    while True:
        try:
            tt = translator.translate(text, dest='ja')
        # googleがブロック?
        except json.decoder.JSONDecodeError:
            cnt += 1
            if cnt > try_times:  # リトライ回数超えたら終わり
                return
            print('sleep {0}sec (try {1}/{2})...'.format(try_span, cnt, try_times))
            time.sleep(try_span)  # リトライ間隔待つ
        # 他のエラー
        except Exception as e:
            print('[err]: {0}'.format(type(e)))
            print('e.args: {0}'.format(e.args))
            print('e: {0}'.format(e))
            return
        else:
            return tt

if __name__ == '__main__':

    psr = argparse.ArgumentParser()
    psr.add_argument('infname', help='入力ファイル名。pdfまたはテキストファイル。')
    psr.add_argument('-o', '--outdir', help='出力ディレクトリ。\
                     省略した場合はカレントディレクトリに出力されます。', default='')
    psr.add_argument('-f', '--formatted', help='整形済み。\
                     余分な改行の削除などの整形が終わっているテキストファイルを入力する場合指定してください。',
                     action='store_true')
    psr.add_argument('-t', '--trytimes', help='google翻訳が返答しない場合にリトライする回数。default 5。',
                     type=int, default=5)
    psr.add_argument('-s', '--tryspan', help='google翻訳が返答しない場合にリトライする間隔(秒)。default 5。',
                     type=int, default=5)
    args = psr.parse_args()

    infbase, _ = os.path.splitext(os.path.basename(args.infname))

    t = time.localtime()
    print('{0:02}:{1:02}:{2:02} start ----------------#'.format(t.tm_hour, t.tm_min, t.tm_sec))  # 開始時刻print

    # pdf
    mob = re.search(r'[^\/]*\.[pP][dD][fF]$', args.infname)
    if mob:

        if args.formatted:
            print('pdfではオプション -f (--formatted) は指定できません。', file=sys.stderr)
            sys.exit()

        # pdfからテキストに
        print('getting text from pdf..')
        raw_text = parse_pdf(args.infname)
        # 中間ファイルに書き出す
        ppfname = os.path.join(args.outdir, '{0}_parse_pdf.txt'.format(infbase))
        print('\t{0} writing..'.format(ppfname))
        with open(ppfname, 'w', encoding='utf-8') as pf:
            pf.write(raw_text)

    # テキストファイル
    else:
        raw_text = read_text(args.infname)

    # 整形済みか
    if args.formatted:
        org_text = raw_text
    else:
        print('formatting..')
        org_text = format_text(raw_text)  # 整形処理
        # 中間ファイルに書き出す
        orgfname = os.path.join(args.outdir, '{0}_original.txt'.format(infbase))
        print('\t{0} writing..'.format(orgfname))
        with open(orgfname, 'w', encoding='utf-8') as of:
            of.write(org_text)

    # proxyチェック
    print('checking proxy..')
    if chk_proxy():
        sys.exit()  # エラー終了

    # 翻訳
    print('translating..')
    jp_text = []
    org_text = org_text.split('\n')
    print_interval = -(-len(org_text) // 20)  # 経過print用
    for i, ot in enumerate(org_text):
        if ot:  # 空行は翻訳に投げない
            ttj = try_translate(ot, try_span=args.tryspan, try_times=args.trytimes)
            if ttj:
                jp_text.append(ttj.text)
            # 翻訳できなかったとき
            else:
                print('section {0} not translated.'.format(i+1))
                jp_text.append(ot)  # 元のtextを入れとく
        else:
            jp_text.append(ot)  # 空行
        if (i + 1) % print_interval == 0:  # 5%ぐらいごとに経過printする
            print('  {:2.0f}%..'.format(i / len(org_text) * 100))
    print(' 100%.')

    # 翻訳文書き出す
    jp_text = '\n'.join(jp_text) + '\n'
    jpfname = os.path.join(args.outdir, '{0}_japanese.txt'.format(infbase))
    print('\t{0} writing..'.format(jpfname))
    with open(jpfname, 'w', encoding='utf-8') as jf:
        jf.write(jp_text)

    print('done.')
