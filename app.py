# -*- coding: utf-8 -*-
import os
import time
import uuid
import json
from flask import Flask, request, render_template, make_response
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError, LineBotApiError
from linebot.models import MessageEvent, TextMessage, TextSendMessage, ImageSendMessage, ImageMessage
import boto3
from botocore.exceptions import BotoCoreError, ClientError

# Flaskアプリケーションの設定
app = Flask(__name__, static_url_path='/static', static_folder='static')

# ==== LINE Bot API設定 ====
LINE_CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.environ.get("LINE_CHANNEL_SECRET")
AWS_ACCESS_KEY_ID = os.environ.get("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY")
AWS_S3_BUCKET_NAME = os.environ.get("AWS_S3_BUCKET_NAME")
AWS_S3_REGION = os.environ.get("AWS_S3_REGION", "us-east-1")

missing_env_vars = []
if not LINE_CHANNEL_ACCESS_TOKEN:
    missing_env_vars.append("LINE_CHANNEL_ACCESS_TOKEN")
if not LINE_CHANNEL_SECRET:
    missing_env_vars.append("LINE_CHANNEL_SECRET")
if not AWS_ACCESS_KEY_ID:
    missing_env_vars.append("AWS_ACCESS_KEY_ID")
if not AWS_SECRET_ACCESS_KEY:
    missing_env_vars.append("AWS_SECRET_ACCESS_KEY")
if not AWS_S3_BUCKET_NAME:
    missing_env_vars.append("AWS_S3_BUCKET_NAME")
if missing_env_vars:
    raise ValueError(f"Missing required environment variables: {', '.join(missing_env_vars)}")

try:
    line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
except LineBotApiError as e:
    raise ValueError(f"Invalid LINE_CHANNEL_ACCESS_TOKEN: {str(e)}")

handler = WebhookHandler(LINE_CHANNEL_SECRET)

# ==== AWS S3設定 ====
s3_client = boto3.client(
    "s3",
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    region_name=AWS_S3_REGION
)

# ==== S3状態保存キー ====
STATE_FILE_KEY = "app_state.json"

# ==== 状態変数（初期化） ====
user_states = {}  # {user_id: {"current_q": int, "answers": [list of answers], "game_cleared": bool, "another_count": int, "is_processing": bool}}
pending_judges = []  # [{"user_id": str, "qnum": int, "img_url": str, "token": str}]
judged_history = []  # [{"user_id": str, "qnum": int, "img_url": str, "result": str, "token": str}]
used_tokens = set()  # 使用済みトークンを追跡

# ==== S3から状態をロード ====
def load_state_from_s3():
    global user_states, pending_judges, judged_history, used_tokens
    try:
        response = s3_client.get_object(Bucket=AWS_S3_BUCKET_NAME, Key=STATE_FILE_KEY)
        state_data = json.loads(response['Body'].read().decode('utf-8'))
        user_states = state_data.get("user_states", {})
        pending_judges = state_data.get("pending_judges", [])
        judged_history = state_data.get("judged_history", [])
        used_tokens = set(state_data.get("used_tokens", []))
        print("State loaded from S3 successfully.")
    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchKey':
            print("No state file found in S3. Initializing empty state.")
        else:
            print(f"Error loading state from S3: {str(e)}")
    except Exception as e:
        print(f"Unexpected error loading state: {str(e)}")

# ==== S3に状態を保存（競合防止） ====
def save_state_to_s3():
    state_data = {
        "user_states": user_states,
        "pending_judges": pending_judges,
        "judged_history": judged_history,
        "used_tokens": list(used_tokens)
    }
    try:
        # 状態保存前に最新状態を再ロード
        try:
            response = s3_client.get_object(Bucket=AWS_S3_BUCKET_NAME, Key=STATE_FILE_KEY)
            current_state = json.loads(response['Body'].read().decode('utf-8'))
            for user_id, state in current_state.get("user_states", {}).items():
                if user_id not in user_states:
                    user_states[user_id] = state
            pending_judges.extend([j for j in current_state.get("pending_judges", []) if j not in pending_judges])
            judged_history.extend([j for j in current_state.get("judged_history", []) if j not in judged_history])
            used_tokens.update(current_state.get("used_tokens", []))
        except ClientError as e:
            if e.response['Error']['Code'] != 'NoSuchKey':
                print(f"Error reloading state from S3: {str(e)}")
        # 保存
        s3_client.put_object(
            Bucket=AWS_S3_BUCKET_NAME,
            Key=STATE_FILE_KEY,
            Body=json.dumps(state_data, ensure_ascii=False).encode('utf-8'),
            ContentType='application/json'
        )
        print("State saved to S3 successfully.")
    except ClientError as e:
        print(f"S3 error saving state: {str(e)} - Code: {e.response.get('Error', {}).get('Code', 'N/A')}")
        raise
    except Exception as e:
        print(f"Unexpected error saving state to S3: {str(e)}")
        raise

# アプリロード時に状態をロード（Render.com対応）
load_state_from_s3()

# ==== 謎の問題データ ====
questions = [
    {
        "story_messages": [
            {"text": '''『第１章』
「やっほー！新米探偵さん！」
画面に探偵姿の少女が現れ、元気に言った。
「わたしは探偵所の新人サポート AI,サクラだよ。よろしくねー！」''', "delay_seconds": 1},
            {"image_url": "https://nazotoki-bot-4-7-9hls.onrender.com/static/smartphone.jpg", "delay_seconds": 0},
            {"text": '''「ここに来てるってことは、君は探偵見習いだよね？」
「サクラの仕事は、 忙しいオサダ所長に代わって新人さんの推理力を鍛えること！」
「では早速、問題です！探偵見習いのテストです。制限時間は……所長が帰ってくるまでにしましょう。困ったら頭をひっくり返して、最初から考えてみるといいですよ。」''', "delay_seconds": 2}
        ],
        "image_url": {"url": "https://nazotoki-bot-4-7-9hls.onrender.com/static/question1.jpg", "delay_seconds": 1},
        "hint_keyword": "101",
        "hint_text": "「手の本数に着目してみたらどうでしょうか？さらにヒントが欲しければ110と送ってください。」",
        "correct_answer": "たんてい"
    },
    {
        "story_messages": [
            {"text": '''『第２章』
「ご名答、です！やっぱりオサダ探偵事務所の一員たるもの、英語くらいできませんとね！さすが、サクラが見込んだだけありました！」
「ではでは新米さん。次の……いや、もう時間みたいですね」
サクラが画面からフェードアウトするのと所長室の扉が開くのはほぼ同時だった。
「すみません、長々とお待たせしたうえで恐縮ですが……」
 申し訳ないが急用が入ってしまった、 とのことでオサダとの面接は後日ということになった。
 挨拶して事務所を出る、と同時にスマホの通知音が鳴った。
「お疲れ様です！面接までの間もサクラがみっちり育ててあげますからね！優秀なあなたをサクラが鍛えたら 120%受かりますから！帰ってから問題三昧です、覚悟しておいてくださいね！」''', "delay_seconds": 1},
            {"text": '''高らかに笑うサクラをこっそりミュートにし、ネットサーフィンを始める。何となく検索エンジンを立ち上げ、適当に面白そうな記事を見ることにした。タイトルはこうだ。
『特集 オサダ探偵社のシャーロック・ホームズ』
「何でミュートにするんですか！」サクラがニュース記事に割り込むように話を始めた。
「サクラを差しおいて、一体何を……ああ、これですか」
それは名探偵カエデを取り上げた記事だった。
レトロな雰囲気にしたいのかモノクロの写真を使っている。
【明治時代からの貴族の令嬢】【大学を飛び級で首席卒業】といった肩書の中にこれまで解決した事件の難解さと鮮やかな手際が事細かに書かれている。
圧倒されるほどの輝かしい経歴を眺めていると、
「噓ばっかり……【削除済み】」
一瞬サクラのメッセージが見えた気がしたが瞬きの合間に消えた。
すぐにいつもの調子でサクラが元気に話しかけてくる。
「どうですか、探偵カエデの活躍を見て？ あなたもこんな風になれるよう頑張りましょう！謎も難しいですよ、探偵所のはチュートリアルみたいなものですからね！というわけで今日の一問！頭をひっくり返して解いてくださいね」''', "delay_seconds": 3}
        ],
        "image_url": {"url": "https://nazotoki-bot-4-7-9hls.onrender.com/static/question2.jpg", "delay_seconds": 1},
        "hint_keyword": "210",
        "hint_text": "「問題文の矢印。何を意味しているんでしょうね？さらにヒントが欲しければ201と送ってください。」",
        "correct_answer": "image_based"
    },
    {
        "story_messages": [
            {"text": '''『第３章』
「ご名答です！ あなたもいずれは名探偵になって、新聞記事に乗る日が来るんですよ。それって、すっごく誇らしいことなんです。探偵として、人々のために働けたことの証、ですからね。やっぱり、新米さんもそのために探偵を目指したんですか？」
それに対してノーと言うと、サクラは「ふーん」と言った。
「そうですか。なら、推理小説が好きだからですか？あ、推理小説と言えば……」
「ノックスの十戒って知ってますか？推理小説が守るべきルールのことで謎解きをフェアにするためにあるんです。最近は守られないことも多いですけどね」
「実際の事件はもっとつまらなかったりしますよ。センセーショナルな難事件よりも単な通り魔の犯行なんかの方がよっぽど多い。そんな事件には『名探偵』も形無しです」
いつも陽気なサクラにしては珍しく毒づくようなことを言う。''', "delay_seconds": 1},
            {"text": "「さて、 雑談もこの辺に、 次の問題です！難しいですよ、頭をぐるぐる回して考えてみてください」おもむろにサクラはいつもの調子を取り戻した。", "delay_seconds": 3}
        ],
        "image_url": {"url": "https://nazotoki-bot-4-7-9hls.onrender.com/static/question3.jpg", "delay_seconds": 1},
        "hint_keyword": "300",
        "hint_text": '''「この法則でいくと……他にはこんな感じですかね？
『［365］◯⚪︎◯◯←◯◯◯→らいねん』
さらにヒントが欲しければ301と送ってください。」''',
        "correct_answer": "じこし"
    },
    {
        "story_messages": [
            {"text": '''『第４章』
「正解です。ま、実際のところ、探偵は事故で呼ばれたりはしませんからね。基本的には縁がないものです。殺人事件に思われたが実は事故だった、事故と思われたけど実は殺人だった、みたいな話はちらほらありますよ。」
サクラは「伝聞なんですけどね」と付け足して、軽く笑い飛ばした。それに少し引っかかることがあって、質問をしようとした矢先のことだった。着信音、電話だった。
「お待たせして申し訳ありません」電話の主、オサダの話はそう始まった。
オサダからの電話の内容はこうだった。「ようやくまとまった時間を取れたから明日の昼から面接をしよう」と。直前まで外せない用事があるそうで、何とかして時間を捻出したと言っていた。
それからしばらくして。
「新米さんは、探偵ってどんな仕事だと思います？」
サクラの問いかけはいつも唐突だ。ただ、 この時の質問は普段とは違う気がした。''', "delay_seconds": 1},
            {"text": '''「一つだけ、サクラからアドバイスがあります。探偵としての心構えについて」
「探偵というのは、悪い仕事です」
「探偵は人の真実を暴きます。正義のために。それが常にいいことという保証はない、そこを理解しないといけないと、私は思っています」
そこまで言ったところでサクラは急に口ごもった。
しばらくして、何もなかったかのようにサクラが再び口を開いた。
「新米さん、アドバイスの続きです。問題を用意しました。 実際の事件を基にした推理小説風の問題です、頭をフル回転して解いてくださいね」''', "delay_seconds": 3}
        ],
        "image_url": {"url": "https://nazotoki-bot-4-7-9hls.onrender.com/static/question4.jpg", "delay_seconds": 1},
        "hint_keyword": "411",
        "hint_text": "「1人ずつ犯人だと仮定して矛盾が生じるか見てみましょう。さらにヒントが欲しければ401と送ってください。」",
        "correct_answer": "Dさん"
    },
    {
        "story_messages": [
            {"text": '''『第５章』
「正解です。 実際の事件では、 いろいろと複雑な関係があったらしいですけどね」
妙に淡々とした口調のまま、サクラは解説を終わらせた。
その日に感じた違和感はぬぐえないまま一日が過ぎ、面接当日になった。
「新米さんもいよいよ面接ですか！頑張ってくださいね」サクラから声をかけてくる。
「本当ならこれからサクラの出番なんですけど、これまででサクラの仕事は終わったみたいです、免許皆伝というやつですか」''', "delay_seconds": 1},
            {"text": '''次のメッセージまでには間があった。メッセージを送る時に深呼吸を挟んだような、そんなわずかな間が。
「これで私の役目は終わりです。でも、一つだけわがままを聞いてください。最後の問題です。」
そう言ってサクラは、たった一言質問した。
「私は、誰ですか？」''', "delay_seconds": 3}
        ],
        "image_url": {"url": "https://nazotoki-bot-4-7-9hls.onrender.com/static/question5.jpg", "delay_seconds": 1},
        "hint_keyword": "",
        "hint_text": "",
        "correct_answer": "image_based",
        "good_end_story": [
            {"text": "→『GOOD END』", "delay_seconds": 1},
            {"text": '''名探偵の記事、探偵についての言葉、これまでの謎、すべてが答えを示していた。ならば、行くべき場所は分かり切っている。
電車に乗り、地図を開き、受付で事務所の関係者を名乗り、エレベーターに乗り、目的の扉を探し当て、ノックをし、部屋に入る。''', "delay_seconds": 2},
            {"image_url": "https://nazotoki-bot-4-7-9hls.onrender.com/static/hospital.jpg", "delay_seconds": 0},
            {"text": '''「正解だよ、新米君」そう言って病室の主、カエデは笑った。''', "delay_seconds": 1},
            {"text": '''事件は終わった。カエデを事故死に見せかけて殺そうとした人物、オサダは逮捕された。オサダ探偵社は事件を作り『名探偵』に解かせるマッチポンプを長らく行っており、事実に気づいたカエデを抹殺しようとしたということらしい。
カエデは探偵を辞めた。後継者として自分を指名し、 探偵社再建の費用として多額の振り込みを探偵社の口座にした後、いつの間にかいなくなっていた。
一枚の手紙を残して。
手紙には振り込んだお金の推奨する使い道やメディア向けのアプローチなどが事細かく書かれたあと、最後の一行にそっけない走り書きが添えてあった。
「私を助けてくれて、ありがとう」
カエデが言うほど、探偵は悪い仕事でないかもしれない。たった 2MB の『AI』の謎解きが、一人の人を救ったのだから。''', "delay_seconds": 2}
        ],
        "bad_end_story": [
            {"text": "→『BAD END』", "delay_seconds": 1},
            {"text": '''「正解です。流石ですね」そう答えたサクラの返事は、ひどく無機質なものに思えた。
その後、サクラが一言も話すことはなかった。
探偵社までの電車に乗っている最中。車内に衝撃的なニュースが流れていた。
「名探偵カエデ 死亡」数時間前入院している病室に何者かが侵入し、銃で撃たれ殺されたらしい。
探偵社に着いた時、オサダは沈痛とした表情を浮かべていた。
オサダはカエデへの哀悼の言葉を口にした後、事務的に面接を始めた。
面接の間ずっと、 オサダの眼は少し濁った緑色をして、こちらを見つめていた。''', "delay_seconds": 2}
        ]
    }
]

# ==== 関数: 問題またはストーリーを送信 ====
def send_content(user_id, content_type, content_data):
    print(f"send_content: user_id={user_id}, content_type={content_type}, current_q={user_states.get(user_id, {}).get('current_q', 'N/A')}")
    try:
        if content_type == "question":
            q = content_data
            for story_msg in q["story_messages"]:
                if "text" in story_msg:
                    line_bot_api.push_message(user_id, TextSendMessage(text=story_msg["text"]))
                elif "image_url" in story_msg:
                    line_bot_api.push_message(
                        user_id,
                        ImageSendMessage(
                            original_content_url=story_msg["image_url"],
                            preview_image_url=story_msg["image_url"]
                        )
                    )
                time.sleep(story_msg["delay_seconds"] + 1)
            line_bot_api.push_message(
                user_id,
                ImageSendMessage(original_content_url=q["image_url"]["url"], preview_image_url=q["image_url"]["url"])
            )
            time.sleep(q["image_url"]["delay_seconds"] + 1)
            if "current_q" in user_states[user_id] and user_states[user_id]["current_q"] in [1, 4]:
                message = "答えとなるものの写真を送ってください。"
                if q["hint_keyword"]:
                    message += f" ヒントが欲しい場合には{q['hint_keyword']}と送ってください。"
                line_bot_api.push_message(user_id, TextSendMessage(text=message))
            else:
                message = "答えとなるテキストを送ってください。"
                if q["hint_keyword"]:
                    message += f" ヒントが欲しい場合には{q['hint_keyword']}と送ってください。"
                line_bot_api.push_message(user_id, TextSendMessage(text=message))
        elif content_type == "end_story":
            for story_msg in content_data:
                if "text" in story_msg:
                    line_bot_api.push_message(user_id, TextSendMessage(text=story_msg["text"]))
                elif "image_url" in story_msg:
                    line_bot_api.push_message(
                        user_id,
                        ImageSendMessage(
                            original_content_url=story_msg["image_url"],
                            preview_image_url=story_msg["image_url"]
                        )
                    )
                time.sleep(story_msg["delay_seconds"] + 1)
            time.sleep(2)
            line_bot_api.push_message(
                user_id,
                TextSendMessage(text='''ゲームクリア！お疲れ様でした！
第5問には2つの解答が用意されています。
もう一方の解答もぜひ考えて、試してみてください！
第5問からもう1度プレイしたい場合にはanotherと送ってください。
本日は大高祭3-4HR企画にお越しいいただきありがとうございました！''')
            )
            # 初回クリア時（another_count == 0）にosada1.jpgを送信
            if user_states.get(user_id, {}).get("another_count", 0) == 0:
                osada_image_url = "https://nazotoki-bot-4-7-9hls.onrender.com/static/osada1.jpg"
                line_bot_api.push_message(
                    user_id,
                    ImageSendMessage(
                        original_content_url=osada_image_url,
                        preview_image_url=osada_image_url
                    )
                )
    except LineBotApiError as e:
        print(f"LineBotApiError in send_content: user_id={user_id}, error={str(e)}, status_code={getattr(e, 'status_code', 'N/A')}")
        line_bot_api.push_message(
            user_id,
            TextSendMessage(text="メッセージ送信中にエラーが発生しました。しばらくしてからもう一度試してください。")
        )
        raise

def send_question(user_id, qnum):
    if qnum < len(questions):
        send_content(user_id, "question", questions[qnum])

# ==== Webhookエンドポイント ====
@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers.get("X-Line-Signature", "")
    body = request.get_data(as_text=True)
    print(f"Received body at {os.getcwd()}: {body}")
    print(f"Signature: {signature}")
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        print("Invalid signature error")
        return "Invalid signature", 400
    except Exception as e:
        print(f"Callback error: {str(e)}")
        return "Internal server error", 500
    return "OK", 200

# ==== メッセージ受信時の処理（テキスト） ====
@handler.add(MessageEvent, message=TextMessage)
def handle_text(event):
    user_id = event.source.user_id
    text = event.message.text.strip().replace('\u3000', '')
    print(f"handle_text: user_id={user_id}, text={text}, user_state={user_states.get(user_id, {})}")

    # 処理中チェック
    if user_id in user_states and user_states[user_id].get("is_processing", False):
        print(f"handle_text: Skipping due to is_processing=True for user_id={user_id}")
        return

    try:
        # 処理開始
        if user_id in user_states:
            user_states[user_id]["is_processing"] = True
        else:
            user_states[user_id] = {"current_q": 0, "answers": [], "game_cleared": False, "another_count": 0, "is_processing": True}
        save_state_to_s3()

        ignore_numbers = ["110", "111", "201", "211", "301", "311", "401", "410"]
        if text in ignore_numbers:
            return

        # ゲーム開始（1回のみ）
        if text.lower() == "start":
            if user_id in user_states and user_states[user_id].get("current_q", 0) > 0:
                return  # 2度目のstartは無反応
            try:
                user_states[user_id] = {"current_q": 0, "answers": [], "game_cleared": False, "another_count": 0, "is_processing": True}
                save_state_to_s3()
                send_question(user_id, 0)
            except Exception as e:
                print(f"Error in handle_text (start): {str(e)}")
                line_bot_api.reply_message(
                    event.reply_token,
                    TextSendMessage(text="サーバーエラー：状態の保存に失敗しました。もう一度試してください。")
                )
            return

        # 第5問再プレイ（2回まで）
        if text.lower() == "another":
            try:
                if user_id not in user_states:
                    user_states[user_id] = {"current_q": 4, "answers": [], "game_cleared": False, "another_count": 1, "is_processing": True}
                else:
                    another_count = user_states[user_id].get("another_count", 0)
                    if another_count >= 2:
                        line_bot_api.reply_message(
                            event.reply_token,
                            TextSendMessage(text="これ以上再プレイできません。本日は3-4HR企画にお越しいいただきありがとうございました。")
                        )
                        return
                    user_states[user_id]["current_q"] = 4
                    user_states[user_id]["game_cleared"] = False
                    user_states[user_id]["another_count"] = another_count + 1
                save_state_to_s3()
                send_question(user_id, 4)
            except Exception as e:
                print(f"Error in handle_text (another): {str(e)}")
                line_bot_api.reply_message(
                    event.reply_token,
                    TextSendMessage(text="サーバーエラー：状態の保存に失敗しました。もう一度試してください。")
                )
            return

        # ユーザー状態のチェック
        if user_id in user_states:
            state = user_states[user_id]
            
            # ゲームクリア後の場合
            if state.get("game_cleared", False):
                if state.get("another_count", 0) >= 2:
                    line_bot_api.reply_message(
                        event.reply_token,
                        TextSendMessage(text="これ以上再プレイできません。本日は3-4HR企画にお越しいただきありがとうございました。")
                    )
                else:
                    line_bot_api.reply_message(
                        event.reply_token,
                        TextSendMessage(text="第5問からもう1度プレイしたい場合にはanotherと送ってください。")
                    )
                return

            # 問題処理ロジック
            qnum = state["current_q"]
            if qnum < len(questions):
                q = questions[qnum]
                if q["hint_keyword"] and text.lower() == q["hint_keyword"].lower():
                    line_bot_api.reply_message(
                        event.reply_token,
                        TextSendMessage(text=q["hint_text"])
                    )
                    return
                elif qnum in [1, 4]:
                    line_bot_api.reply_message(
                        event.reply_token,
                        TextSendMessage(text="画像で解答してください。")
                    )
                    return
                elif isinstance(q["correct_answer"], str) and q["correct_answer"] != "image_based" and text.lower() == q["correct_answer"].lower():
                    try:
                        user_states[user_id]["current_q"] += 1
                        save_state_to_s3()
                        send_question(user_id, user_states[user_id]["current_q"])
                    except Exception as e:
                        print(f"Error in handle_text (correct answer): {str(e)}")
                        line_bot_api.reply_message(
                            event.reply_token,
                            TextSendMessage(text="サーバーエラー：状態の保存に失敗しました。もう一度試してください。")
                        )
                    return
                else:
                    if qnum in [0, 2, 3]:
                        line_bot_api.reply_message(
                            event.reply_token,
                            TextSendMessage(text=f"「ブブー、不正解です。もしもヒントが欲しければ、{q['hint_keyword']}と送ってください。」")
                        )
                    return

        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="まずはstartと送って始めてね")
        )
    finally:
        # 処理終了
        if user_id in user_states:
            user_states[user_id]["is_processing"] = False
            save_state_to_s3()

# ==== 画像メッセージ処理（S3アップロード対応） ====
@handler.add(MessageEvent, message=ImageMessage)
def handle_image(event):
    user_id = event.source.user_id
    print(f"handle_image: user_id={user_id}, user_state={user_states.get(user_id, {})}")

    if user_id not in user_states:
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="まずはstartと送って始めてね"))
        return

    qnum = user_states[user_id]["current_q"]
    if qnum not in [1, 4]:
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="この問題はテキストで解答してください"))
        return

    try:
        message_content = line_bot_api.get_message_content(event.message.id)
        unique_filename = f"{user_id}_{qnum}_{uuid.uuid4()}.jpg"
        file_bytes = b"".join([chunk for chunk in message_content.iter_content(chunk_size=1024)])

        s3_client.put_object(Bucket=AWS_S3_BUCKET_NAME, Key=unique_filename, Body=file_bytes, ACL='public-read', ContentType='image/jpeg')
        s3_url = f"https://{AWS_S3_BUCKET_NAME}.s3.{AWS_S3_REGION}.amazonaws.com/{unique_filename}"

        token = str(uuid.uuid4())
        pending_judges.append({"user_id": user_id, "qnum": qnum, "img_url": s3_url, "token": token})
        save_state_to_s3()

        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="判定中です。しばらくお待ちください。"))

    except LineBotApiError as e:
        print(f"LineBotApiError in handle_image: user_id={user_id}, error={str(e)}, status_code={getattr(e, 'status_code', 'N/A')}")
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="サーバーエラー：API接続に失敗しました。"))
    except PermissionError as pe:
        print(f"Permission error in handle_image: {str(pe)}")
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="サーバーエラー：書き込み権限がありません。"))
    except IOError as ioe:
        print(f"IO error in handle_image: {str(ioe)}")
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="サーバーエラー：ファイル操作に失敗しました。"))
    except Exception as e:
        print(f"Unexpected error in handle_image: {str(e)}")
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="画像の処理中にエラーが発生しました。もう一度試してください。"))

# ==== 判定フォーム ====
@app.route("/judge", methods=["GET", "POST"])
def judge():
    global pending_judges, judged_history, used_tokens

    if request.method == "POST":
        user_id = request.form.get("user_id")
        qnum = request.form.get("qnum")
        result = request.form.get("result")
        token = request.form.get("token")

        if token in used_tokens:
            print(f"Duplicate request detected for token: {token}")
            return "Duplicate request", 400

        if user_id and qnum and result and token:
            try:
                qnum = int(qnum)
                judge_to_process = next((j for j in pending_judges if j["user_id"] == user_id and j["qnum"] == qnum and j["token"] == token), None)
                if judge_to_process:
                    used_tokens.add(token)
                    if qnum == 4:
                        if result == "good_end":
                            user_states[user_id]["game_cleared"] = True
                            send_content(user_id, "end_story", questions[qnum]["good_end_story"])
                        elif result == "bad_end":
                            user_states[user_id]["game_cleared"] = True
                            send_content(user_id, "end_story", questions[qnum]["bad_end_story"])
                        elif result == "retry":
                            line_bot_api.push_message(
                                user_id,
                                TextSendMessage(text="「ブブー、不正解です。別の画像を送ってください。もしもヒントが欲しければ周囲の事務所スタッフに聞いてみてください。")
                            )
                    else:
                        if result == "correct":
                            if user_id in user_states:
                                user_states[user_id]["current_q"] += 1
                                send_question(user_id, user_states[user_id]["current_q"])
                        elif result == "incorrect":
                            line_bot_api.push_message(
                                user_id,
                                TextSendMessage(text=f"「ブブー、不正解です。もしもヒントが欲しければ、{questions[qnum]['hint_keyword']}と送ってください。」")
                            )

                    judged_history.append({
                        "user_id": user_id,
                        "qnum": qnum,
                        "img_url": judge_to_process["img_url"],
                        "result": result,
                        "token": token
                    })
                    pending_judges = [j for j in pending_judges if not (j["user_id"] == user_id and j["qnum"] == qnum and j["token"] == token)]
                    save_state_to_s3()
            except LineBotApiError as e:
                print(f"LineBotApiError in judge: user_id={user_id}, error={str(e)}, status_code={getattr(e, 'status_code', 'N/A')}")
                return "API error", 500
            except ValueError:
                print(f"Invalid qnum in judge: {qnum}")
                return "Invalid data", 400

    response = make_response(render_template("judge.html", judges=pending_judges, history=judged_history))
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    return response

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
