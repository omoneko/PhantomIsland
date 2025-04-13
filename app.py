from flask import Flask, jsonify, request, session, send_from_directory
import json
import copy
import os

app = Flask(__name__)
app.secret_key = "your_secret_key_here"

# map.json 読み込み
with open("map.json", encoding="utf-8") as f:
    map_data = json.load(f)

def get_sim_data():
    """セッション上のシミュレーション用データ (map.json の 'bases' コピー)"""
    if "sim_data" not in session:
        session["sim_data"] = copy.deepcopy(map_data["bases"])
    return session["sim_data"]

def set_sim_data(data):
    session["sim_data"] = data
    session.modified = True

def get_adventure_groups():
    """冒険団データ: { group_name: { raw_active_value, active_total, battle_values[], territory } }"""
    if "adventure_groups" not in session:
        session["adventure_groups"] = {}
    return session["adventure_groups"]

def set_adventure_groups(advs):
    session["adventure_groups"] = advs
    session.modified = True

# ----------------------------------------------
# 文字入力された活力値を数値に変換 (例: '3億' => 300000000)
# ----------------------------------------------
def parse_active_value(raw_val):
    s = str(raw_val).strip()
    if not s:
        return 0.0
    s = s.replace(",", "")

    factor = 1
    if "億" in s:
        s = s.replace("億", "")
        factor *= 100_000_000
    if "万" in s:
        s = s.replace("万", "")
        factor *= 10_000
    try:
        base_val = float(s)
    except ValueError:
        base_val = 0.0
    return base_val * factor

# ----------------------------------------------
# 8チーム前提の脅威度計算 (ratio = sum(battle_values)/active_total)
# 上位2=>高, 中4=>中, 下2=>低
# ----------------------------------------------
def compute_threat_levels():
    advs = get_adventure_groups()
    if len(advs) < 8:
        return {}
    data_list = []
    for name, info in advs.items():
        bsum = sum(info.get("battle_values", []))
        a_val = info.get("active_total", 0)
        ratio = 0
        if a_val != 0:
            ratio = bsum / a_val
        data_list.append((name, ratio))

    data_list.sort(key=lambda x: x[1], reverse=True)
    result_map = {}
    top8 = data_list[:8]  # 8チーム以上あれば先頭8件のみ
    for i, (g, r) in enumerate(top8):
        if i < 2:
            result_map[g] = "高"
        elif i < 6:
            result_map[g] = "中"
        else:
            result_map[g] = "低"
    return result_map

# ----------------------------------------------
# チーム別合計スコア計算
# - owner_team == team => 0
# - それ以外 => node["score"]
# - 非陣地でも node["score"] を加算
# ----------------------------------------------
def calc_team_scores(sim_data):
    scores = {}
    for nd in sim_data.values():
        t = nd.get("team")
        if not t:
            continue
        if t not in scores:
            scores[t] = 0
        if nd["type"] == "陣地":
            # 初期拠点:0, その他:score
            if nd.get("owner_team") == t:
                scores[t] += 0
            else:
                scores[t] += nd.get("score", 0)
        else:
            # 陣地以外 (コンビニ等)
            scores[t] += nd.get("score", 0)
    return scores

# ----------------------------------------------
# /api/map
#   マップ用データ返却
#   - raw_active_value => display_active
#   - 合計スコア => display_score
#   - 脅威度 => threat
# ----------------------------------------------
@app.route("/api/map", methods=["GET"])
def api_map():
    sim_data = get_sim_data()
    advs = get_adventure_groups()
    threats = compute_threat_levels()

    # チーム別合計スコア
    team_scores = calc_team_scores(sim_data)

    for node_id, node in sim_data.items():
        tname = node.get("team")

        # 活力値は raw_active_value をそのまま表示させる
        # -> display_active
        if node["type"] == "陣地":
            if tname and tname in advs:
                node["display_active"] = advs[tname].get("raw_active_value", "0")
            else:
                node["display_active"] = ""
            # 合計スコアをマップに表示したいなら => display_score= team_scores.get(tname, 0)
            node["display_score"] = team_scores.get(tname, 0) if tname else 0
        else:
            # 陣地以外でもdisplay_scoreをチーム合計にするなら以下
            node["display_active"] = ""
            node["display_score"] = team_scores.get(tname, 0) if tname else 0

        # 脅威度
        if tname in threats:
            node["threat"] = threats[tname]
        else:
            node["threat"] = ""

    return jsonify(sim_data)

# ----------------------------------------------
# /api/scores
#   得点表示欄用 => チーム別合計
# ----------------------------------------------
@app.route("/api/scores", methods=["GET"])
def api_scores():
    sim_data = get_sim_data()
    result = calc_team_scores(sim_data)
    return jsonify(result)

# ----------------------------------------------
# /api/reset
#   シミュレーション + 冒険団リセット
# ----------------------------------------------
@app.route("/api/reset", methods=["POST"])
def api_reset():
    sim_reset = copy.deepcopy(map_data["bases"])
    set_sim_data(sim_reset)
    session.pop("adventure_groups", None)
    return jsonify({"message": "マップ & 冒険団情報をリセットしました"})

# ----------------------------------------------
# /api/assign_team
#   マップ上でチームを割り当て (クリック etc.)
#   冒険団が未登録なら自動作成
# ----------------------------------------------
@app.route("/api/assign_team", methods=["POST"])
def api_assign_team():
    data = request.get_json()
    node_id = data.get("node_id")
    tname = data.get("team","").strip()
    sim_data = get_sim_data()

    if not node_id or node_id not in sim_data:
        return jsonify({"error": "不正なノードIDです"}), 400

    node = sim_data[node_id]
    if node["type"] == "陣地" and not node.get("team"):
        node["owner_team"] = tname
    node["team"] = tname
    set_sim_data(sim_data)

    advs = get_adventure_groups()
    if tname not in advs:
        advs[tname] = {
            "raw_active_value":"0",
            "active_total": 0,
            "battle_values": [0,0,0,0,0],
            "territory": node_id
        }
    else:
        advs[tname]["territory"] = node_id
    set_adventure_groups(advs)

    return jsonify({"message": f"{node_id} を {tname} が占領"})

# ----------------------------------------------
# /api/adventure_groups (GET/POST)
#   - GET: 全冒険団一覧
#   - POST: 新規 or 更新
# ----------------------------------------------
@app.route("/api/adventure_groups", methods=["GET","POST"])
def api_adventure_groups():
    if request.method == "GET":
        advs = get_adventure_groups()
        result = []
        for nm, val in advs.items():
            result.append({
                "group_name": nm,
                "raw_active_value": val.get("raw_active_value","0"),
                "active_total": val.get("active_total",0),
                "battle_values": val.get("battle_values",[]),
                "territory": val.get("territory","")
            })
        return jsonify(result)
    else:
        posted = request.get_json()
        gname = posted.get("group_name","").strip()
        if not gname:
            return jsonify({"error":"冒険団名は必須です"}),400

        raw_active = posted.get("active_total","0")
        numeric_active = parse_active_value(raw_active)
        bvals = posted.get("battle_values",[])
        bvals = [float(x) for x in bvals]

        territory = posted.get("territory","").strip()

        advs = get_adventure_groups()
        advs[gname] = {
            "raw_active_value": raw_active,
            "active_total": numeric_active,
            "battle_values": bvals,
            "territory": territory
        }
        set_adventure_groups(advs)

        # 同時に陣地へチームを反映
        sim_data = get_sim_data()
        if territory in sim_data and sim_data[territory].get("type")=="陣地":
            if not sim_data[territory].get("team"):
                sim_data[territory]["owner_team"] = gname
            sim_data[territory]["team"] = gname
            set_sim_data(sim_data)

        return jsonify({"message": f"冒険団『{gname}』を登録/更新しました (陣地: {territory})"})

# ----------------------------------------------
# index.html を返す
# ----------------------------------------------
@app.route("/")
def index():
    return send_from_directory("static","index.html")

@app.route("/favicon.ico")
def favicon():
    return "", 204

if __name__ == "__main__":
    port = int(os.environ.get("PORT",5000))
    app.run(host="0.0.0.0", port=port, debug=False)
