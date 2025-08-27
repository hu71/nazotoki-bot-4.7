import os
import time
import uuid
from flask import Flask, request, render_template
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError, LineBotApiError
from linebot.models import MessageEvent, TextMessage, TextSendMessage, ImageSendMessage, ImageMessage

# Flaskアプリケーションの設定
app = Flask(__name__, static_url_path='/static', static_folder='static')

# ==== LINE Bot API設定 ====
LINE_CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.environ.get("LINE_CHANNEL_SECRET")

if not LINE_CHANNEL_ACCESS_TOKEN or not LINE_CHANNEL_SECRET:
    raise ValueError("LINE_CHANNEL_ACCESS_TOKEN and LINE_CHANNEL_SECRET must be set in environment variables.")

try:
    line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
except LineBotApiError as e:
    raise ValueError(f"Invalid LINE_CHANNEL_ACCESS_TOKEN: {str(e)}")

handler = WebhookHandler(LINE_CHANNEL_SECRET)

# ==== 謎の問題データ ====
questions = [
    {
        "story_messages": [
            {"text": '''「やっほー！新米探偵さん！」
            「わたしは探偵所の新人サポート AI,サクラだよ。よろしくねー！」
            「ここに来てるってことは、君は探偵見習いだよね？」
            「サクラの仕事は、 忙しいオサダ所長に代わって新人さんの推理力を鍛えること！」''', "delay_seconds": 2}
            {"text": '''「では早速、問題！探偵見習いのテストだよ。
            制限時間は……所長が帰ってくるまでにしましょう。
            困ったら頭をひっくり返して、最初から考えてみるといいですよ。」''', "delay_seconds": 2}
        ],
        "image_url": {"url": "https://drive.google.com/uc?export=view&id=17HLOeJgb6cPCMZfVlBKRUYs67wqZOEY_", "delay_seconds": 1},
        "hint_keyword": "hint1",
        "hint_text": "第1問のヒントです",
        "correct_answer": "correct1"
    },
    {
        "story_messages": [
            {"text": '''「ご名答、です！やっぱりオサダ探偵事務所の一員たるもの、英語くらいできませんとね！さすが、サクラが見込んだだけありました！」
            「ではでは新米さん。次の……いや、もう時間みたいですね」
            サクラが画面からフェードアウトするのと所長室の扉が開くのはほぼ同時だった。
            「すみません、長々とお待たせしたうえで恐縮ですが……」
            申し訳ないが急用が入ってしまった、 とのことでオサダとの面接は後日ということになった。
            挨拶して事務所を出る、と同時にスマホの通知音が鳴った。
            「お疲れ様です！面接までの間もサクラがみっちり育ててあげますからね！優秀なあなたをサクラが鍛えたら 120%受かりますから！帰ってから問題三昧です、覚悟しておいてくださいね！」
            {"text": '''ネットサーフィンをしていると一つの記事が目に留まった。
            「特集 オサダ探偵所のシャーロック・ホームズ」
            カエデを取り上げた記事だ。
            【明治時代からの貴族の令嬢】【大学を飛び級で首席卒業】といった肩書の中にこれまで解決した事件の難解さと鮮やかな手際が事細かに書かれている。
            圧倒されるほどの輝かしい経歴を眺めていると
            「噓ばっかり……【削除済み】」
            一瞬サクラのメッセージが見えた気がしたが瞬きの合間に消えた。
            すぐにいつもの調子でサクラが元気に話しかけてくる。
            「どうですか、探偵カエデの活躍を見て？ あなたもこんな風になれるよう頑張りましょう！謎も難しいですよ、 事務所のはチュートリアルみたいなものですからね！というわけで今日の一問！困ったら頭をひっくり返して、ですよ」", "delay_seconds": 2}
        ],
        "image_url": {"url": "https://drive.google.com/uc?export=view&id=16hDDwLKg7gf367LT32kxUF5rAfThU66S", "delay_seconds": 1},
        "hint_keyword": "hint2",
        "hint_text": "第2問のヒントです",
        "correct_answer": "correct2"
    },
    {
        "story_messages": [
            {"text": '''「ご名答、です！ マッチポンプ、盗みの予告状を自分の下に出したり、難事件を紐解くとかなりあるんですよねー。探偵カエデの解決した事件にもそんな事件がいくつかあったらしいですよ？例えば……」
            またしてもサクラが勝手に喋り出す。
          「ノックスの十戒って知ってますか？推理小説が守るべきルールのことで謎解きをフェアにするためにあるんです。最近は守られないことも多いですけどね」
          「実際の事件はもっとつまらなかったりしますよ。センセーショナルな難事件よりも単な通り魔の犯行なんかの方がよっぽど多い。そんな事件には『名探偵』も形無しです」
          いつも陽気なサクラにしては珍しく毒づくようなことを言う。''', "delay_seconds": 2},
            {"text": "「さて、雑談もこの辺に、次の問題です！難しいですよ、頭をぐるぐる回して考えてみてください」", "delay_seconds": 2}
        ],
        "image_url": {"url": "https://drive.google.com/uc?export=view&id=12D6c3LtrlXnuUcmc4vNxPq-aLeUw3Ukd", "delay_seconds": 1},
        "hint_keyword": "hint3",
        "hint_text": "第3問のヒントです",
        "correct_answer": "correct3"
    },
    {
        "story_messages": [
            {"text": '''「正解です！ 事故死と言っても、探偵は事故で呼ばれたりはしませんからねー。基本的には縁がないものです。殺人事件に思われたが実は事故だった、事故と思われたけど実は殺人だった、みたいな話はちらほらありますけどね」
            「お待たせして申し訳ありません」
            オサダからの電話はそう始まった。ようやくまとまった時間を取れるようになったようだ。
            明日の昼からということになった。 直前まで外せない用事があるそうで、 何とかして時間を捻出したと言っていた。それからしばらくして。
            「新米さんは、探偵ってどんな仕事だと思います？」
            サクラの問いかけはいつも唐突だ。ただこの時の質問はいつもとは違う気がした。''', "delay_seconds": 2},
            {"text": '''「一つだけ、サクラからアドバイスがあります。探偵としての心構えについて」
            「探偵というのは、悪い仕事です」
            「探偵は人の真実を暴きます。正義のために。それが常にいいことという保証はない、そこを理解しないといけないと、私は思っています」
            そこまで言ったところでサクラは急に口ごもった。しばらくして、何もなかったかのようにサクラが再び口を開いた。
            「新米さん、アドバイスの続きです。問題を用意しました。実際の事件を基にした推理小説風の問題です、頭をフル回転して解いてくださいね」''', "delay_seconds": 2}
        ],
        "image_url": {"url": "https://drive.google.com/uc?export=view&id=1tmzcdvKHBUBvggOfv-gj-P0w7FdoZeWw", "delay_seconds": 1},
        "hint_keyword": "hint4",
        "hint_text": "第4問のヒントです",
        "correct_answer": "correct4"
    },
    {
        "story_messages": [
            {"text": '''「正解です。実際の事件では、いろいろと複雑な関係があったらしいですけどね」
            妙に淡々とした口調のまま、サクラは解説を終わらせた。
            そして数日が過ぎ、面接当日になった。
            「新米さんもいよいよ面接ですか！頑張ってくださいね」
            サクラから声をかけてくる。
            「本当ならこれからサクラの出番なんですけど、これまででサクラの仕事は終わったみたいです、免許皆伝というやつですか」", "delay_seconds": 2},
            {"text": '''次のメッセージまでには間があった。メッセージを送る時に深呼吸を挟んだような、そんなわずかな間が。
            「これで私の役目は終わりです。でも、一つだけわがままを聞いてください。最後の問題です。」
            そう言ってサクラは、たった一言質問した。
            「私は、誰ですか？」''', "delay_seconds": 2}
        ],
        "image_url": {"url": "https://drive.google.com/uc?export=view&id=1lUYDFR6pVpyZxCB4JC2pkxS8dYZXZlT8", "delay_seconds": 1},
        "hint_keyword": "hint5",
        "hint_text": "第5問のヒントです",
        "correct_answer": ["カエデ", "サクラ"],
        "good_end_story": [
            {"text": "→『GOOD END』", "delay_seconds": 1},
            {"text": '''名探偵の記事、探偵についての言葉、これまでの謎、すべてが答えを示していた。
            ならば、行くべき場所は分かり切っている。
            電車に乗り、地図を開き、受付で事務所の関係者を名乗り、エレベーターに乗り、目的の扉を探し当て、ノックをし、部屋に入る。
            「正解だよ、新米君」そう言って病室の主、カエデは笑った。
            「そして最終回詐欺だ新米君。本当の最後の謎、私が君に伝えたかったことは？」''', "delay_seconds": 2}
        ],
        "bad_end_story": [
            {"text": "→『BAD END』", "delay_seconds": 1},
            {"text": '''「正解です。流石ですね」
            そう答えたサクラの返事は、ひどく無機質なものに思えた。その後、サクラが一言も話すことはなかった。
            事務所までの電車に乗っている最中。車内に衝撃的なニュースが流れていた。
            「名探偵カエデ 死亡」数時間前入院している病室に何者かが侵入し、銃で撃たれ殺されたらしい。
            事務所に着いた時、オサダは沈痛とした表情を浮かべていた。オサダはカエデへの哀悼の言葉を口にした後、事務的に面接を始めた。
            面接の間ずっと、オサダの眼は少し濁った緑色をして、こちらを見つめていた。''', "delay_seconds": 2}
        ]
    }
]

# ==== ユーザーごとの進行状況と回答 ====
user_states = {}  # {user_id: {"current_q": int, "answers": [list of answers], "game_cleared": bool}}
pending_judges = []     # [{"user_id": str, "qnum": int, "img_url": str}]
judged_history = []     # [{"user_id": str, "qnum": int, "img_url": str, "result": str}]

# ==== 関数: 問題またはストーリーを送信 ====
def send_content(user_id, content_type, content_data):
    try:
        if content_type == "question":
            q = content_data
            for story_msg in q["story_messages"]:
                line_bot_api.push_message(user_id, TextSendMessage(text=story_msg["text"]))
                time.sleep(story_msg["delay_seconds"])
            line_bot_api.push_message(
                user_id,
                ImageSendMessage(original_content_url=q["image_url"]["url"], preview_image_url=q["image_url"]["url"])
            )
            time.sleep(q["image_url"]["delay_seconds"])
            if "current_q" in user_states[user_id] and user_states[user_id]["current_q"] == 1:  # 第2問の場合
                line_bot_api.push_message(user_id, TextSendMessage(text="答えとなるものの写真を送ってね！"))
            else:
                line_bot_api.push_message(user_id, TextSendMessage(text="答えとなるテキストを送ってね！"))
        elif content_type == "end_story":
            for story_msg in content_data:
                line_bot_api.push_message(user_id, TextSendMessage(text=story_msg["text"]))
                time.sleep(story_msg["delay_seconds"])
            line_bot_api.push_message(user_id, TextSendMessage(text="ゲームクリア！お疲れ様でした！"))
    except LineBotApiError as e:
        print(f"Failed to send content to {user_id}: {str(e)} - Status code: {getattr(e, 'status_code', 'N/A')}")
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
    text = event.message.text.strip()

    # ゲーム開始
    if text.lower() == "start":
        user_states[user_id] = {"current_q": 0, "answers": [], "game_cleared": False}
        send_question(user_id, 0)
        return

    # ユーザー状態のチェック
    if user_id in user_states:
        state = user_states[user_id]
        
        # ゲームクリア後の場合
        if state.get("game_cleared", False):
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="もう一度プレイしたい場合にはstartと送ってね")
            )
            return

        # 問題処理ロジック
        qnum = state["current_q"]
        if qnum < len(questions):
            q = questions[qnum]
            if text.lower() == q["hint_keyword"].lower():
                line_bot_api.reply_message(
                    event.reply_token,
                    TextSendMessage(text=q["hint_text"])
                )
                return
            elif qnum == 1:  # 第2問は画像解答なのでテキストでは不正解
                line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"画像で解答してください。{q['hint_keyword']}と送ると何かあるかも"))
                return
            elif qnum < 4 and text.lower() == q["correct_answer"].lower():  # 1,3,4問目はテキスト解答
                user_states[user_id]["current_q"] += 1
                line_bot_api.reply_message(event.reply_token, TextSendMessage(text="大正解！"))
                send_question(user_id, user_states[user_id]["current_q"])
                return
            elif qnum == 4 and text.lower() in q["correct_answer"]:  # 第5問の正解1/2
                user_states[user_id]["game_cleared"] = True  # ゲームクリア状態をTrueに
                if text.lower() == q["correct_answer"][0]:  # カエデ → Goodエンド
                    send_content(user_id, "end_story", q["good_end_story"])
                elif text.lower() == q["correct_answer"][1]:  # サクラ → Badエンド
                    send_content(user_id, "end_story", q["bad_end_story"])
                return
            else:  # その他の不正解
                line_bot_api.reply_message(
                    event.reply_token,
                    TextSendMessage(text=f"残念。不正解です。{q['hint_keyword']}と送ると何かあるかも")
                )
                return

    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text="メッセージを理解できませんでした。")
    )

# ==== 画像メッセージ受信時の処理 ====
@handler.add(MessageEvent, message=ImageMessage)
def handle_image(event):
    user_id = event.source.user_id

    if user_id not in user_states:
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="まずは『start』と送って始めてね！"))
        return

    qnum = user_states[user_id]["current_q"]

    if qnum != 1:  
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="この問題はテキストで解答してください。"))
        return

    try:
        print(f"Fetching image for user {user_id}, question {qnum}")
        message_content = line_bot_api.get_message_content(event.message.id)
        
        # 一意のファイル名を生成
        unique_filename = f"{user_id}_{qnum}_{uuid.uuid4()}.jpg"
        temp_path = f"/tmp/{unique_filename}"
        os.makedirs("/tmp", exist_ok=True)
        with open(temp_path, "wb") as f:
            for chunk in message_content.iter_content(chunk_size=1024):
                f.write(chunk)

        if not os.path.exists(temp_path):
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="サーバーエラー：画像を保存できませんでした。"))
            return

        # 静的フォルダにコピー
        static_path = os.path.join(app.static_folder, unique_filename)
        with open(static_path, "wb") as f:
            with open(temp_path, "rb") as temp_f:
                f.write(temp_f.read())

        # ホストURLを安全に取得
        host_url = request.host_url if request.host_url else os.environ.get("RENDER_EXTERNAL_URL", "https://nazotoki-bot-4-7-2.onrender.com")
        img_url = f"{host_url.rstrip('/')}/static/{unique_filename}"
        pending_judges.append({"user_id": user_id, "qnum": qnum, "img_url": img_url})

        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="判定中です。しばらくお待ちください！"))

    except LineBotApiError as e:
        print(f"LineBotApi error: {str(e)} - Status code: {getattr(e, 'status_code', 'N/A')}, Error details: {getattr(e, 'error_details', 'N/A')}")
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="サーバーエラー：API接続に失敗しました。"))
    except PermissionError as pe:
        print(f"Permission error: {str(pe)}")
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="サーバーエラー：書き込み権限がありません。"))
    except IOError as ioe:
        print(f"IO error: {str(ioe)}")
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="サーバーエラー：ファイル操作に失敗しました。"))
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="画像の処理中にエラーが発生しました。もう一度試してください。"))

# ==== 判定フォーム ====
@app.route("/judge", methods=["GET", "POST"])
def judge():
    global pending_judges, judged_history

    if request.method == "POST":
        user_id = request.form.get("user_id")
        qnum = request.form.get("qnum")
        result = request.form.get("result")

        # POSTデータが全て揃っていて、pending_judgesに該当データがある場合のみ処理
        if user_id and qnum and result:
            try:
                qnum = int(qnum)
                # 対応するpending_judgesエントリが存在するか確認
                judge_to_process = next((j for j in pending_judges if j["user_id"] == user_id and j["qnum"] == qnum), None)
                if judge_to_process:
                    if result == "correct":
                        line_bot_api.push_message(user_id, TextSendMessage(text="大正解！"))
                        if user_id in user_states:
                            user_states[user_id]["current_q"] += 1
                            send_question(user_id, user_states[user_id]["current_q"])
                    else:
                        line_bot_api.push_message(user_id, TextSendMessage(text="残念。不正解です。もう一度挑戦してみよう！"))

                    judged_history.append({
                        "user_id": user_id,
                        "qnum": qnum,
                        "img_url": judge_to_process["img_url"],
                        "result": result
                    })
                    pending_judges = [j for j in pending_judges if not (j["user_id"] == user_id and j["qnum"] == qnum)]
            except LineBotApiError as e:
                print(f"Failed to send result to {user_id}: {str(e)} - Status code: {getattr(e, 'status_code', 'N/A')}")
                return "API error", 500
            except ValueError:
                print(f"Invalid qnum: {qnum}")
                return "Invalid data", 400

    return render_template("judge.html", judges=pending_judges, history=judged_history)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
