import os
import time
from flask import Flask, request
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError, LineBotApiError
from linebot.models import MessageEvent, TextMessage, TextSendMessage, ImageSendMessage, ImageMessage

# Flaskアプリケーションの設定
app = Flask(__name__)

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
            {"text": "「やっほー！新米探偵さん！」", "delay_seconds": 2},
            {"text": "「わたしは探偵所の新人サポート AI,サクラだよ。よろしくねー！」", "delay_seconds": 2},
            {"text": "「ここに来てるってことは、君は探偵見習いだよね？」", "delay_seconds": 2},
            {"text": "「サクラの仕事は、 忙しいオサダ所長に代わって新人さんの推理力を鍛えること！」", "delay_seconds": 2},
            {"text": "「では早速、問題！探偵見習いのテストだよ。制限時間は……所長が帰ってくるまでにしましょう。困ったら頭をひっくり返して、最初から考えてみるといいですよ。」", "delay_seconds": 2}
        ],
        "image_url": {"url": "https://drive.google.com/uc?export=view&id=17HLOeJgb6cPCMZfVlBKRUYs67wqZOEY_", "delay_seconds": 1},
        "hint_keyword": "hint1",
        "hint_text": "第1問のヒントです",
        "correct_answer": "correct1"
    },
    {
        "story_messages": [
            {"text": "「ご名答、です！やっぱりオサダ探偵事務所の一員たるもの、英語くらいできませんとね！さすが、サクラが見込んだだけありました！」", "delay_seconds": 2},
            {"text": "「ではでは新米さん。次の……いや、もう時間みたいですね」", "delay_seconds": 2},
            {"text": "(サクラが画面からフェードアウトするのと所長室の扉が開くのはほぼ同時だった。)", "delay_seconds": 2},
            {"text": "「すみません、長々とお待たせしたうえで恐縮ですが……」", "delay_seconds": 2},
            {"text": "(申し訳ないが急用が入ってしまった、 とのことでオサダとの面接は後日ということになった。挨拶して事務所を出る、と同時にスマホの通知音が鳴った。)", "delay_seconds": 2},
            {"text": "「お疲れ様です！面接までの間もサクラがみっちり育ててあげますからね！優秀なあなたをサクラが鍛えたら 120%受かりますから！帰ってから問題三昧です、覚悟しておいてくださいね！」", "delay_seconds": 2},
            {"text": "(ネットサーフィンをしていると一つの記事が目に留まった。)", "delay_seconds": 2},
            {"text": "「特集 オサダ探偵所のシャーロック・ホームズ」", "delay_seconds": 2},
            {"text": "(カエデを取り上げた記事だ。【明治時代からの貴族の令嬢】【大学を飛び級で首席卒業】といった肩書の中にこれまで解決した事件の難解さと鮮やかな手際が事細かに書かれている。圧倒されるほどの輝かしい経歴を眺めていると、)", "delay_seconds": 2},
            {"text": "「噓ばっかり……【削除済み】」", "delay_seconds": 2},
            {"text": "(一瞬サクラのメッセージが見えた気がしたが瞬きの合間に消えた。すぐにいつもの調子でサクラが元気に話しかけてくる。)", "delay_seconds": 2},
            {"text": "「どうですか、探偵カエデの活躍を見て？ あなたもこんな風になれるよう頑張りましょう！謎も難しいですよ、 事務所のはチュートリアルみたいなものですからね！というわけで今日の一問！困ったら頭をひっくり返して、ですよ」", "delay_seconds": 2}
        ],
        "image_url": {"url": "https://drive.google.com/uc?export=view&id=16hDDwLKg7gf367LT32kxUF5rAfThU66S", "delay_seconds": 1},
        "hint_keyword": "hint2",
        "hint_text": "第2問のヒントです",
        "correct_answer": "correct2"
    },
    {
        "story_messages": [
            {"text": "「ご名答、です！ マッチポンプ、盗みの予告状を自分の下に出したり、難事件を紐解くとかなりあるんですよねー。探偵カエデの解決した事件にもそんな事件がいくつかあったらしいですよ？例えば……」", "delay_seconds": 2},
            {"text": "(またしてもサクラが勝手に喋り出す。)", "delay_seconds": 2},
            {"text": "「ノックスの十戒って知ってますか？推理小説が守るべきルールのことで謎解きをフェアにするためにあるんです。最近は守られないことも多いですけどね」", "delay_seconds": 2},
            {"text": "「実際の事件はもっとつまらなかったりしますよ。センセーショナルな難事件よりも単な通り魔の犯行なんかの方がよっぽど多い。そんな事件には『名探偵』も形無しです」", "delay_seconds": 2},
            {"text": "(いつも陽気なサクラにしては珍しく毒づくようなことを言う。)", "delay_seconds": 2},
            {"text": "「さて、雑談もこの辺に、次の問題です！難しいですよ、頭をぐるぐる回して考えてみてください」", "delay_seconds": 2}
        ],
        "image_url": {"url": "https://drive.google.com/uc?export=view&id=12D6c3LtrlXnuUcmc4vNxPq-aLeUw3Ukd", "delay_seconds": 1},
        "hint_keyword": "hint3",
        "hint_text": "第3問のヒントです",
        "correct_answer": "correct3"
    },
    {
        "story_messages": [
            {"text": "「正解です！ 事故死と言っても、探偵は事故で呼ばれたりはしませんからねー。基本的には縁がないものです。殺人事件に思われたが実は事故だった、事故と思われたけど実は殺人だった、みたいな話はちらほらありますけどね」", "delay_seconds": 2},
            {"text": "「お待たせして申し訳ありません」", "delay_seconds": 2},
            {"text": "(オサダからの電話はそう始まった。ようやくまとまった時間を取れるようになったようだ。明日の昼からということになった。 直前まで外せない用事があるそうで、 何とかして時間を捻出したと言っていた。それからしばらくして。)", "delay_seconds": 2},
            {"text": "「新米さんは、探偵ってどんな仕事だと思います？」", "delay_seconds": 2},
            {"text": "(サクラの問いかけはいつも唐突だ。ただこの時の質問はいつもとは違う気がした。)", "delay_seconds": 2},
            {"text": "「一つだけ、サクラからアドバイスがあります。探偵としての心構えについて」", "delay_seconds": 2},
            {"text": "「探偵というのは、悪い仕事です」", "delay_seconds": 2},
            {"text": "「探偵は人の真実を暴きます。正義のために。それが常にいいことという保証はない、そこを理解しないといけないと、私は思っています」", "delay_seconds": 2},
            {"text": "(そこまで言ったところでサクラは急に口ごもった。しばらくして、何もなかったかのようにサクラが再び口を開いた。)", "delay_seconds": 2},
            {"text": "「新米さん、アドバイスの続きです。問題を用意しました。実際の事件を基にした推理小説風の問題です、頭をフル回転して解いてくださいね」", "delay_seconds": 2}
        ],
        "image_url": {"url": "https://drive.google.com/uc?export=view&id=1tmzcdvKHBUBvggOfv-gj-P0w7FdoZeWw", "delay_seconds": 1},
        "hint_keyword": "hint4",
        "hint_text": "第4問のヒントです",
        "correct_answer": "correct4"
    },
    {
        "story_messages": [
            {"text": "「正解です。実際の事件では、いろいろと複雑な関係があったらしいですけどね」", "delay_seconds": 2},
            {"text": "妙に淡々とした口調のまま、サクラは解説を終わらせた。", "delay_seconds": 2},
            {"text": "そして数日が過ぎ、面接当日になった。", "delay_seconds": 2},
            {"text": "「新米さんもいよいよ面接ですか！頑張ってくださいね」", "delay_seconds": 2},
            {"text": "サクラから声をかけてくる。", "delay_seconds": 2},
            {"text": "「本当ならこれからサクラの出番なんですけど、これまででサクラの仕事は終わったみたいです、免許皆伝というやつですか」", "delay_seconds": 2},
            {"text": "次のメッセージまでには間があった。メッセージを送る時に深呼吸を挟んだような、そんなわずかな間が。", "delay_seconds": 2},
            {"text": "「これで私の役目は終わりです。でも、一つだけわがままを聞いてください。最後の問題です。」", "delay_seconds": 2},
            {"text": "そう言ってサクラは、たった一言質問した。", "delay_seconds": 2},
            {"text": "「私は、誰ですか？」", "delay_seconds": 2}
        ],
        "image_url": {"url": "https://drive.google.com/uc?export=view&id=1lUYDFR6pVpyZxCB4JC2pkxS8dYZXZlT8", "delay_seconds": 1},
        "hint_keyword": "hint5",
        "hint_text": "第5問のヒントです",
        "correct_answer": ["カエデ", "サクラ"],
        "good_end_story": [
            {"text": "→『GOOD END』", "delay_seconds": 1},
            {"text": "名探偵の記事、探偵についての言葉、これまでの謎、すべてが答えを示していた。", "delay_seconds": 3},
            {"text": "ならば、行くべき場所は分かり切っている。", "delay_seconds": 2},
            {"text": "電車に乗り、地図を開き、受付で事務所の関係者を名乗り、エレベーターに乗り、目的の扉を探し当て、ノックをし、部屋に入る。", "delay_seconds": 2},
            {"text": "「正解だよ、新米君」そう言って病室の主、カエデは笑った。", "delay_seconds": 2},
            {"text": "「そして最終回詐欺だ新米君。本当の最後の謎、私が君に伝えたかったことは？」", "delay_seconds": 2}
        ],
        "bad_end_story": [
            {"text": "→『BAD END』", "delay_seconds": 1},
            {"text": "「正解です。流石ですね」", "delay_seconds": 2},
            {"text": "そう答えたサクラの返事は、ひどく無機質なものに思えた。その後、サクラが一言も話すことはなかった。", "delay_seconds": 2},
            {"text": "事務所までの電車に乗っている最中。車内に衝撃的なニュースが流れていた。", "delay_seconds": 2},
            {"text": "「名探偵カエデ 死亡」数時間前入院している病室に何者かが侵入し、銃で撃たれ殺されたらしい。", "delay_seconds": 2},
            {"text": "事務所に着いた時、オサダは沈痛とした表情を浮かべていた。オサダはカエデへの哀悼の言葉を口にした後、事務的に面接を始めた。", "delay_seconds": 2},
            {"text": "面接の間ずっと、オサダの眼は少し濁った緑色をして、こちらを見つめていた。", "delay_seconds": 2}
        ]
    }
]

# ==== ユーザーごとの進行状況と回答 ====
user_states = {}  # {user_id: {"current_q": int, "answers": [list of answers], "game_cleared": bool}}

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
    # else節が作用することはなさそう 8/25/10:32 by pernum
    # else:
    #     line_bot_api.push_message(user_id, TextSendMessage(text="全ての問題が終了しました！"))

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
            elif qnum < 4 and text.lower() == q["correct_answer"].lower():  # 1〜4問
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
            else:  # 不正解（第1～5問共通）
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

    # ユーザー状態のチェック
    if user_id in user_states and user_states[user_id].get("game_cleared", False):
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="もう一度プレイしたい場合にはstartと送ってね")
        )
    else:
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="メッセージを理解できませんでした。")
        )

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
