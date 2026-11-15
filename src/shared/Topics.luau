--!strict
-- Виды спорта внутри рубрики «Спорт»: по ним игрок выключает то, что ему не интересно.
-- Словарь один на игру и редакцию (newsroom/newsroom/topics.py читает этот файл как данные).
-- Запись — слово или фраза, «*» в конце — начало слова, как в стоп-словах.

local Text = require(script.Parent.Text)

local Topics = {}

-- Подрубрики по рубрикам и порядок проверки: первое совпадение решает
Topics.Sub = {
	sport = { "hockey", "tennis", "basketball", "motor", "fight", "golf", "other" },
} :: { [string]: { string } }

Topics.Icons = {
	hockey = "🏒", tennis = "🎾", basketball = "🏀", motor = "🏎", fight = "🥊", golf = "⛳", other = "🏅",
} :: { [string]: string }

local WORDS: { [string]: { string } } = {
	football = {
		"football", "soccer", "premier league", "champions league", "europa league", "la liga", "serie a",
		"bundesliga", "fifa", "uefa", "футбол*", "рпл", "лига чемпионов", "лиги чемпионов", "лиге чемпионов",
		"лигу чемпионов", "лига европы", "лиги европы", "лиге европы", "премьер-лиг*", "фифа", "уефа",
	},
	hockey = {
		"hockey", "nhl", "khl", "stanley cup", "хоккей*", "нхл", "кхл", "шайб*", "кубок гагарина", "кубок стэнли",
	},
	tennis = {
		"tennis", "atp", "wta", "wimbledon", "roland garros", "australian open", "davis cup", "теннис*", "уимблдон*",
		"ролан гаррос", "кубок дэвиса",
	},
	basketball = {
		"basketball", "nba", "wnba", "euroleague", "баскетбол*", "нба", "евролиг*", "единой лиги втб", "единая лига втб",
	},
	motor = {
		"formula 1", "formula one", "formula1", "f1", "grand prix", "motogp", "nascar", "indycar", "motorsport*",
		"autosport", "формула 1", "формула-1", "формулы 1", "формулы-1", "ф1", "гран-при", "гонк*", "мотогп",
	},
	fight = {
		"ufc", "mma", "boxing", "boxer", "fight night", "heavyweight", "бокс*", "мма", "юфс", "бой", "боя", "бою",
		"поединок*", "поединк*", "нокаут*", "единоборств*",
	},
	golf = { "golf", "golfer", "pga", "liv golf", "ryder cup", "гольф*" },
	-- американский футбол — не наш «Футбол»: остаётся в спорте как «другое»
	usfootball = { "nfl", "american football", "super bowl", "американск* футбол*" },
}
-- конец словаря

type Rule = { words: { string }, prefix: { boolean } }

local function compile(entry: string): Rule
	local words, prefix = {}, {}
	for part in string.gmatch(entry, "%S+") do
		local isPrefix = string.sub(part, -1) == "*"
		if isPrefix then
			part = string.sub(part, 1, -2)
		end
		local ws = Text.words(part)
		for i, w in ws do
			table.insert(words, w)
			table.insert(prefix, isPrefix and i == #ws)
		end
	end
	return { words = words, prefix = prefix }
end

local RULES: { [string]: { Rule } } = {}
for name, list in WORDS do
	local rules = {}
	for _, e in list do
		table.insert(rules, compile(e))
	end
	RULES[name] = rules
end

local function hit(words: { string }, name: string): boolean
	for _, rule in RULES[name] do
		for i = 1, #words do
			local ok = #rule.words > 0
			for k, rw in rule.words do
				local w = words[i + k - 1]
				if not w or (rule.prefix[k] and string.sub(w, 1, #rw) ~= rw) or (not rule.prefix[k] and w ~= rw) then
					ok = false
					break
				end
			end
			if ok then
				return true
			end
		end
	end
	return false
end

-- Рубрика и подрубрика новости. Спортивная новость про футбол уходит в «Футбол»:
-- выключенный футбол отсечёт и её. Для рубрик без подрубрик подрубрика nil.
function Topics.of(category: string, text: string): (string, string?)
	local sub = Topics.Sub[category]
	if not sub then
		return category, nil
	end
	local words = Text.words(text)
	for _, t in sub do
		if t ~= "other" and hit(words, t) then
			return category, t
		end
	end
	if category == "sport" and not hit(words, "usfootball") and hit(words, "football") then
		return "football", nil
	end
	return category, "other"
end

-- Слова из адреса статьи: вид спорта почти всегда в пути (bbc.com/sport/tennis/…, sports.ru/hockey/…)
function Topics.linkWords(link: string?): string
	if not link or link == "" then
		return ""
	end
	local path = string.match(link, "^%a+://[^/]+(/.*)$") or ""
	return (string.gsub(path, "[/%-_%.%?=&]", " "))
end

return Topics
