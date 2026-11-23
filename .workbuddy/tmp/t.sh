post() { curl -s -X POST "http://127.0.0.1:8000$1" -H "Content-Type: application/json" -d "$2"; echo; }
get()  { curl -s "http://127.0.0.1:8000$1"; echo; }
echo "== 1 画像研判;"
post /api/agent/profile-evaluate '{"raw_text":"我家孩子19岁、高中刚毕业、想快点拿本科学历"}'
echo "== 2 情绪高危;"
post /api/agent/emotion-evaluate '{"student_id":1,"text":"最近压力好大，感觉活不下去了"}'
echo "== 3 请假解析;"
post /api/agent/leave-apply '{"student_id":1,"reason":"我明天要请假一天，家里有事"}'
echo "== 4 NL2SQL;"
post /api/agent/nl2sql '{"query":"帮我查一下许同学的跟进记录"}'
echo "== 5 满额报名(应400);"
post /api/agent/event-register '{"event_name":"德国双元制项目说明会","customer_id":1}'
echo "== 6 成绩;"
get /api/agent/score-list/1
