--!strict
-- Какие заметки нельзя показывать. Roblox запрещает политиков и партии, реальные трагедии, насилие,
-- откровенное и азартные игры (Community Standards, проверено 23.10.2026, ссылки в README).
-- Поэтому ленты берутся только мягких рубрик, а здесь второй слой: стоп-слова и служебные заметки.
-- Правило: «слово» — точное совпадение, «слово*» — начало слова, «два слова» — фраза подряд.

local Text = require(script.Parent.Text)

local Safety = {}

local LISTS: { [string]: { string } } = {
	-- политика и государство
	politics = {
		"trump*", "biden*", "harris", "vance", "obama*", "putin*", "zelensk*", "starmer*", "macron*", "merz",
		"netanyahu*", "erdogan*", "modi", "xi", "kim jong*", "musk*", "farage*", "le pen", "meloni*", "orban*",
		"lula", "milei", "sunak*", "badenoch", "reform uk", "hegseth*", "rubio*", "leavitt*", "newsom*", "desantis*",
		"xi jinping", "king charles", "queen camilla", "princess kate", "kate middleton", "buckingham palace",
		"election*", "elect", "elected", "electoral", "vote*", "voter*", "voting", "ballot*", "referendum*", "midterm*", "poll", "polls",
		"senate*", "senator*", "congress*", "parliament*", "mp", "mps", "minister*", "ministry", "president*",
		"presidency", "government*", "govt", "governor*", "mayor*", "democrat*", "republican*", "gop", "maga",
		"labour", "tory", "tories", "conservatives", "liberals", "politic*", "white house", "kremlin",
		"downing street", "pentagon", "nato", "sanction*", "tariff*", "immigra*", "migrant*", "deport*", "border", "borders",
		"protest*", "riot*", "rally", "regime*", "dictator*", "king charles", "royal family", "prince william",
		"prince harry", "meghan", "doj", "fbi", "cia", "supreme court", "lawmaker*", "legislat*",
		"policy", "policies", "tax", "taxes", "budget", "ukrain*", "russia*", "gaza*", "israel*", "palestin*",
		"iran*", "hamas", "hezbollah", "taiwan*", "crimea*", "kashmir*", "korea north", "north korea*", "houthi*",
		"yemen*", "syria*", "venezuela*", "cuba*", "kyiv", "moscow", "tehran",
		"nazi*", "hitler*", "fascis*", "communis*", "socialis*", "woke", "dei", "transgender", "trans",
		"abortion*", "gender", "pm", "prime minister*", "chancellor*", "attorney general", "welfare", "benefits",
		"pope", "vatican", "church", "mosque", "synagogue", "religio*", "king", "queen", "prince", "princess", "royal",
		"royals", "monarch*",
	},
	-- насилие, смерть, катастрофы, преступления
	violence = {
		"war", "wars", "warfare", "military", "army", "troop*", "soldier*", "missile*", "bomb*", "nuclear",
		"weapon*", "gun", "guns", "gunfire", "gunman", "gunmen", "shooting", "shootings", "shooter*", "shot dead",
		"gunshot*", "stab*", "knife*", "murder*", "kill*", "dead", "dies", "died", "death*", "deadly", "fatal*",
		"funeral*", "passes away", "passed away", "tribute*", "the late",
		"suicid*", "overdose*", "terror*", "attack", "attacks", "attacked", "hostage*", "kidnap*", "abduct*", "massacre*", "genocide*",
		"crash*", "collision", "disaster*", "earthquake*", "hurricane*", "tornado*", "flood*", "wildfire*",
		"tsunami*", "victim*", "injured", "wounded", "blood*", "gore", "violen*", "assault*", "abuse*",
		"beat to death", "beaten to death", "fight for survival", "famine", "refugee*", "conflict*", "invasion*",
		"spy", "spies", "espionage", "cyber attack", "hack*", "explosion*", "fire kills", "cancer*", "tumou*",
		"tumor*", "disease*", "virus*", "pandemic*", "outbreak*", "hospital*", "illness", "diagnos*",
		"arrest*", "charged", "charges", "jail*", "prison*", "sentenc*", "convict*", "trial", "court", "courts",
		"courtroom", "lawsuit*",
		"sue", "sues", "sued", "police", "cop", "cops", "crime*", "criminal*", "fraud*", "scam*", "theft",
		"burgl*", "robbed", "robbery", "stolen", "investigat*", "allegation*", "alleged*", "accus*", "probe",
		"guilty", "dui", "drunk*", "drug*", "cocaine", "heroin", "cannabis", "marijuana", "weed", "vape*",
		"alcohol*", "rehab", "raid", "raided", "stalker*", "stalking", "thief", "thieves", "horror*", "horrific",
		"paralys*", "paralyz*", "agony", "als", "ms", "puberty", "rescue", "rescues", "rescued", "sinking", "age gap", "alive", "sclerosis", "dementia", "autism", "surgery", "battered", "missing",
		"tragic*", "tragedy", "grief", "grieving", "mourn*", "heartbroken", "heartbreak*", "devastat*", "emergency",
		"scary", "terrifying", "terrified", "chilling", "sinister", "macabre", "grim", "lockdown", "evacuat*",
		"hate", "racis*", "racial", "slur*", "extremis*", "toxic", "betrayal", "fuming", "slams", "blasts", "feud*",
		"divorce*", "split", "splits", "breakup", "dumped",
	},
	-- откровенное
	adult = {
		"sex*", "rape*", "raping", "nude*", "naked", "topless", "porn*", "onlyfans", "lingerie", "bikini*",
		"swimsuit*", "plunging", "racy", "steamy", "sultry", "busty", "cleavage", "braless", "underwear",
		"stripper*", "striptease", "escort*", "affair*", "intimate", "erotic*", "fetish*", "kink*", "orgy",
		"condom*", "dating app", "hookup",
	},
	-- азартные игры и реклама
	gambling = {
		"bet", "bets", "betting", "bettor*", "sportsbook*", "casino*", "gambl*", "promo code*", "bonus code*",
		"betting odds", "parlay*", "wager*", "jackpot*", "lottery", "powerball", "crypto*", "bitcoin*", "sale",
		"discount*", "coupon*", "shopping", "buy now", "best buy", "amazon prime day", "black friday",
	},
	-- служебные заметки лент: не заголовок новости
	service = {
		"sign up", "newsletter*", "live", "as it happened", "podcast*", "video", "watch", "quiz*", "wordle",
		"crossword*", "connections", "horoscope*", "opinion", "letters", "obituar*", "recap", "highlights",
		"transcript", "sponsored", "advert*", "review", "reviews", "ranked", "gallery", "photos", "pictures",
		"in pictures", "best buy", "deals", "subscribe",
	},
	-- русская версия: то же по смыслу
	ru = {
		"путин*", "песков*", "зеленск*", "трамп*", "байден*", "лукашенк*", "медведев*", "лавров*", "мишустин*",
		"собянин*", "володин*", "кадыров*", "навальн*", "шойгу", "белоусов*", "захаров*", "кремл*", "госдум*",
		"дума", "думы", "думе", "депутат*", "министр*", "минобороны", "правительств*", "губернатор*", "мэр*",
		"президент*", "сенатор*", "парламент*", "партия", "партии", "партий", "выбор*", "голосован*", "референдум*",
		"санкци*", "политик*", "оппозиц*", "митинг*", "протест*", "иноагент*", "экстремист*", "нежелательн*",
		"сво", "всу", "вс рф", "войн*", "военн*", "армия", "армии", "солдат*", "мобилизац*", "фронт*", "обстрел*",
		"ракет*", "бпла", "беспилотник*", "дрон*", "атак*", "удар по", "ударил*", "взрыв*", "теракт*", "террор*",
		"заложник*", "украин*", "киев*", "донбасс*", "днр", "лнр", "крым*", "херсон*", "запорож*", "курск*",
		"белгород*", "израил*", "газа", "сектор газа", "палестин*", "иран*", "нато", "сша", "пентагон*",
		"погиб*", "гибел*", "убит*", "убил*", "убийств*", "умер*", "умира*", "смерт*", "скончал*", "похорон*",
		"труп*", "тело", "тела", "ранен*", "пострадал*", "травм*", "дтп", "авари*", "катастроф*", "крушен*",
		"пожар*", "землетрясен*", "наводнен*", "ураган*", "цунами", "эвакуац*", "жертв*", "трагед*", "траур*",
		"задержан*", "арест*", "суд", "суда", "суде", "судом", "суды", "судеб*", "приговор*", "уголовн*",
		"следств*", "ск рф", "прокуратур*", "генпрокуратур*", "реабилитац*", "нацизм*", "экстремизм*", "иноагент*", "полиц*", "мвд", "фсб", "силовик*", "мошенни*", "краж*", "украл*", "ограблен*",
		"обыск*", "колони*", "тюрьм*", "срок", "наркот*", "алкогол*", "пьян*", "казино", "ставк*", "букмекер*",
		"секс*", "интим*", "голая", "голый", "обнажен*", "эрот*", "порн*", "откровенн*", "купальник*", "бикини",
		"нижнем белье", "развод*", "измен*", "рак", "онколог*", "болезн*", "болен", "больна", "больниц*",
		"реанимац*", "инсульт*", "инфаркт*", "операци*", "церков*", "патриарх*", "религи*", "мечет*",
		"мигрант*", "нацист*", "фашист*", "лгбт", "скандал*", "оскорбл*", "избил*", "драк*", "насили*",
		"видео", "смотрите", "онлайн", "трансляц*", "прямой эфир", "фото", "тест", "гороскоп*", "реклама",
		"промокод*", "скидк*", "winline", "fonbet", "фонбет", "betboom", "бетбум", "лига ставок", "pari", "марафонбет",
		"пиво", "пива", "пиве", "водк*", "миддлтон", "принц", "принца", "принцесс*", "королевск*", "монарх*",
		"темнокож*", "чернокож*", "расизм*", "расист*",
	},
}

type Rule = { words: { string }, prefix: { boolean } }
local RULES: { [string]: { Rule } } = {}

local function compile(entry: string): Rule
	local words, prefix = {}, {}
	for part in string.gmatch(Text.lower(entry), "%S+") do
		local isPrefix = string.sub(part, -1) == "*"
		if isPrefix then
			part = string.sub(part, 1, -2)
		end
		-- слова правила проходят тот же разбор, что и заголовок
		local ws = Text.words(part)
		for i, w in ws do
			table.insert(words, w)
			table.insert(prefix, isPrefix and i == #ws)
		end
	end
	return { words = words, prefix = prefix }
end

for name, list in LISTS do
	local rules = {}
	for _, e in list do
		table.insert(rules, compile(e))
	end
	RULES[name] = rules
end

local function matchAt(words: { string }, i: number, rule: Rule): boolean
	for k, rw in rule.words do
		local w = words[i + k - 1]
		if not w then
			return false
		end
		if rule.prefix[k] then
			if string.sub(w, 1, #rw) ~= rw then
				return false
			end
		elseif w ~= rw then
			return false
		end
	end
	return true
end

-- Первое сработавшее правило: (список, правило) или nil
function Safety.check(text: string, extra: { string }?): (string?, string?)
	local words = Text.words(text)
	for name, rules in RULES do
		for _, rule in rules do
			for i = 1, #words do
				if matchAt(words, i, rule) then
					return name, table.concat(rule.words, " ")
				end
			end
		end
	end
	if extra then
		for _, e in extra do
			local rule = compile(e)
			for i = 1, #words do
				if matchAt(words, i, rule) then
					return "extra", e
				end
			end
		end
	end
	return nil, nil
end

-- Добавить список стоп-слов (например, русский) под именем
function Safety.addList(name: string, list: { string })
	local rules = RULES[name] or {}
	for _, e in list do
		table.insert(rules, compile(e))
	end
	RULES[name] = rules
end

return Safety
