"""오프라인 단위 테스트(번역기 호출 없음): python -m unittest test_nlp"""

import unittest

from german import decompose_de
from targets import decompose_ja, decompose_en, decompose_ko, hanja_reading_matches, looks_like_transliteration, _split_loan
from translator import GtxTranslator


def lemmas(units):
    return [[m.lemma for m in u.morphemes] for u in units]


class GermanTests(unittest.TestCase):
    def test_compound_with_link(self):
        units, links = decompose_de("Abfahrtszeit")
        self.assertEqual(lemmas(units), [["ab", "Fahrt"], ["Zeit"]])
        self.assertEqual(links, ["s"])

    def test_agent_suffix_restores_infinitive(self):
        units, _ = decompose_de("Kugelschreiber")
        self.assertEqual(lemmas(units), [["Kugel"], ["schreiben", "-er"]])

    def test_simplex_not_split(self):
        for w in ("Haus", "Schmetterling", "Zeitung", "Finger"):
            self.assertEqual(len(decompose_de(w)[0]), 1, w)

    def test_prefix_umlaut_stem_and_suffix(self):
        # ungefährlich = un + gefähr(← Gefahr) + -lich  (CharSplit 이 'Ungefähr + lich'로 끊던 것)
        units, _ = decompose_de("ungefährlich")
        self.assertEqual([[m.lemma for m in u.morphemes] for u in units], [["un", "Gefahr", "-lich"]])
        self.assertEqual([m.role for m in units[0].morphemes], ["prefix", "root", "suffix"])

    def test_gesellschaft_is_geselle_plus_schaft(self):
        # 어간 Geselle 는 흔하지 않아서 예전엔 분해하지 못했다 (+e 복원 + -schaft 의 낮은 문턱)
        units, _ = decompose_de("Gesellschaft")
        self.assertEqual([[m.lemma for m in u.morphemes] for u in units], [["Geselle", "-schaft"]])

    def test_derivational_tail_is_not_a_compound_part(self):
        for w in ("Freundschaft", "Gesundheit", "Möglichkeit"):
            units, _ = decompose_de(w)
            self.assertEqual(len(units), 1, w)  # 한 단어 안의 어근 + 접미사
            self.assertEqual(units[0].morphemes[-1].role, "suffix", w)

    def test_derivational_tail_attached(self):
        units, _ = decompose_de("Gesundheit")
        self.assertEqual(len(units), 1)


class TargetTests(unittest.TestCase):
    def test_hanja_reading(self):
        self.assertEqual(hanja_reading_matches("출발", "出発"), ["出", "発"])
        self.assertEqual(hanja_reading_matches("이상", "理想"), ["理", "想"])  # 두음법칙
        self.assertIsNone(hanja_reading_matches("장갑", "手袋"))
        self.assertIsNotNone(hanja_reading_matches("운전면허증", "運転免許証"))  # 証(정)은 證(증)의 신자체

    def test_transliteration(self):
        self.assertTrue(looks_like_transliteration("볼펜", "ボールペン"))
        self.assertTrue(looks_like_transliteration("컴퓨터", "コンピューター"))
        self.assertFalse(looks_like_transliteration("책상", "デスク"))
        self.assertFalse(looks_like_transliteration("접근", "アクセス"))

    def test_loan_split(self):
        self.assertEqual(_split_loan("볼펜", "ボールペン"), [("볼", "ボール"), ("펜", "ペン")])

    def test_japanese(self):
        self.assertEqual([u.text for u in decompose_ja("ボールペン")], ["ボール", "ペン"])
        self.assertEqual([u.text for u in decompose_ja("手袋")], ["手", "袋"])
        self.assertEqual([u.text for u in decompose_ja("出発時間")], ["出発", "時間"])

    def test_japanese_sino_is_word_level(self):
        # 한어는 글자가 아니라 단어 단위 형태소 (한국어 한자어와 같은 깊이)
        self.assertEqual([[m.surface for m in u.morphemes] for u in decompose_ja("病院")], [["病院"]])
        self.assertEqual([[m.surface for m in u.morphemes] for u in decompose_ja("出発時間")], [["出発"], ["時間"]])
        self.assertEqual([[(m.surface, m.role) for m in u.morphemes] for u in decompose_ja("冷蔵庫")], [[("冷蔵", "root"), ("庫", "suffix")]])

    def test_japanese_okurigana_compounds_split(self):
        # 활용한 모양의 읽기(取り=トリ)로 비교해야 오쿠리가나 합성어가 쪼개진다
        for whole, parts in [("取り消し", ["取り", "消し"]), ("払い戻し", ["払い", "戻し"]), ("回り道", ["回り", "道"]), ("申し込み", ["申し", "込み"])]:
            self.assertEqual([u.text for u in decompose_ja(whole)], parts, whole)

    def test_japanese_non_compositional_stay_whole(self):
        for w in ("今日", "大人", "田舎", "彼女", "時計", "八百屋"):
            self.assertEqual(len(decompose_ja(w)), 1, w)

    def test_japanese_na_ending_is_suffix(self):
        # 無害+な : 형용동사의 어미 な 를 접미사 형태소로 (독일어 -lich 와 짝지어진다)
        ms = decompose_ja("無害な")[0].morphemes
        self.assertEqual([(m.surface, m.role) for m in ms], [("無害", "root"), ("な", "suffix")])

    def test_japanese_i_adjective_stays_whole(self):
        # 美し+い 처럼 활용 꼬리를 떼지 않는다 (명사 토큰만 훈독 합성어로 쪼갠다)
        for w in ("美しい", "明るい"):
            self.assertEqual([u.text for u in decompose_ja(w)], [w])

    def test_japanese_native_and_loan_unchanged(self):
        self.assertEqual([[m.surface for m in u.morphemes] for u in decompose_ja("手袋")], [["手"], ["袋"]])
        self.assertEqual([[m.surface for m in u.morphemes] for u in decompose_ja("ボールペン")], [["ボール"], ["ペン"]])
        # 숙자훈(어종 和)은 글자별로 쪼개지 않는다
        self.assertEqual([[m.surface for m in u.morphemes] for u in decompose_ja("今日")], [["今日"]])

    def test_english_latin_prefix(self):
        # 독일어 ab+fahr+t 와 같은 깊이: 접두사 + 어근 + 접미사
        self.assertEqual([(m.surface, m.role) for m in decompose_en("departure")[0].morphemes],
                         [("de", "prefix"), ("part", "root"), ("-ure", "suffix")])
        # 굳어진 흔한 단어·남는 부분이 단어가 아닌 경우는 그대로
        for w in ("report", "carpet", "hospital", "reason", "detail"):
            self.assertEqual(len(decompose_en(w)[0].morphemes), 1, w)

    def test_english_suffix_restores_enter(self):
        # entrance = enter + -ance : 접미사를 떼면 e 가 -er 자리에서 밀려난다
        ms = decompose_en("entrance")[0].morphemes
        self.assertEqual([(m.surface, m.lemma, m.role) for m in ms], [("entr", "enter", "root"), ("-ance", "-ance", "suffix")])
        self.assertIn(decompose_en("central")[0].morphemes[0].lemma, ("center", "centre"))
        # 기존 복원은 그대로
        self.assertEqual([m.lemma for m in decompose_en("importance")[0].morphemes], ["import", "-ance"])
        self.assertEqual([m.lemma for m in decompose_en("closure")[0].morphemes][0], "close")
        # 모음 뒤의 r 은 건드리지 않는다
        self.assertEqual(len(decompose_en("general")[0].morphemes), 1)

    def test_english_adjective_suffixes(self):
        for w, parts in [("harmless", ["harm", "-less"]), ("dangerous", ["danger", "-ous"]), ("careful", ["care", "-ful"])]:
            self.assertEqual([m.surface for m in decompose_en(w)[0].morphemes], parts, w)
        # happiness = happy + -ness (i → y 복원)
        ms = decompose_en("happiness")[0].morphemes
        self.assertEqual([(m.lemma, m.role) for m in ms], [("happy", "root"), ("-ness", "suffix")])
        # 접미사 단어를 합성어로 쪼개지 않는다: 하나의 단위(unit) 안의 어근+접미사
        self.assertEqual(len(decompose_en("hopeless")), 1)

    def test_english(self):
        self.assertEqual([u.text for u in decompose_en("ballpoint pen")], ["ball", "point", "pen"])
        self.assertEqual([u.text for u in decompose_en("carpet")], ["carpet"])
        self.assertEqual([m.surface for m in decompose_en("departure")[0].morphemes], ["de", "part", "-ure"])


if __name__ == "__main__":
    unittest.main()


class MultiWordSinoTests(unittest.TestCase):
    """번역기 호출이 필요한 테스트(캐시가 있으면 오프라인으로도 통과). 단어 경계는 일본어 분석기로 얻는다."""

    @classmethod
    def setUpClass(cls):
        cls.tr = GtxTranslator()

    def groups(self, word):
        return [[m.surface for m in u.morphemes] for u in decompose_ko(word, self.tr)]

    def test_vacuum_cleaner_is_three_words(self):
        self.assertEqual(self.groups("진공청소기"), [["진공"], ["청소"], ["기"]])

    def test_prefix_syllable_not_dropped(self):
        self.assertEqual(self.groups("대학교"), [["대"], ["학교"]])

    def test_single_word_is_not_split_into_characters(self):
        self.assertEqual(self.groups("병원"), [["병원"]])
        self.assertEqual(self.groups("세탁기"), [["세탁"], ["기"]])

    def test_adjective_ending_is_suffix(self):
        # 무해 + 한(하+ㄴ), 부정 + 적
        self.assertEqual([[(m.surface, m.role) for m in u.morphemes] for u in decompose_ko("무해한", self.tr)], [[("무해", "root"), ("한", "suffix")]])
        self.assertEqual([[(m.surface, m.role) for m in u.morphemes] for u in decompose_ko("부정적인", self.tr)], [[("부정", "root"), ("적", "suffix")]])

    def test_matches_japanese_depth(self):
        # 같은 단어를 한국어/일본어가 같은 개수의 단위·형태소로 본다
        self.assertEqual(self.groups("냉장고"), [["냉장", "고"]])
        self.assertEqual([[m.surface for m in u.morphemes] for u in decompose_ja("冷蔵庫")], [["冷蔵", "庫"]])


class AlignmentTests(unittest.TestCase):
    """번역기 캐시를 쓰는 통합 테스트."""

    @classmethod
    def setUpClass(cls):
        from pipeline import analyze

        cls.tr = GtxTranslator()
        cls.analyze = staticmethod(analyze)

    def target(self, word, lang):
        a = self.analyze(word, self.tr)
        return next(t for t in a["targets"] if t["lang"] == lang)

    def test_sino_word_aligns_one_to_one(self):
        # 세탁 = wasch, 기 = Maschine : 글자 단위로 쪼개지 않으니 '추가' 요소가 남지 않는다
        ko = self.target("Waschmaschine", "ko")
        self.assertEqual([g["relation"] for g in ko["alignment"]].count("added"), 0)
        self.assertEqual([g["target"] for g in ko["alignment"]], [[0], [1]])

    def test_single_german_unit_vs_multi_part_target_is_same_meaning(self):
        # 독일어가 한 단어(예: 파생어 Lehrer = Lehr+er)이고 대응어가 여러 요소면 뜻은 같음. (형태소 1개짜리 단어는 이제 진단 전에 멈추므로 align 을 직접 시험)
        from align import align
        from units import Morpheme, Unit

        class NoSignal:
            def lookup(self, *a, **k):
                return []

            lookup_pos = lookup

        de = [Unit("Lehrer", [Morpheme("Lehr", "lehren", role="root"), Morpheme("-er", "-er", role="suffix")])]
        target = [Unit("x", [Morpheme("x", "x", role="root")]), Unit("y", [Morpheme("y", "y", role="root")])]
        groups, _, _ = align(de, target, "en", NoSignal(), "Lehrer")
        self.assertEqual([g["relation"] for g in groups], ["same"])
        self.assertEqual(groups[0]["target"], [0, 1])

    def test_single_sino_word_vs_compound_is_merged_like_hospital(self):
        # 병원은 한 단어(형태소 1개)라서 hospital·病院 과 똑같이 krank+Haus 와 한 그룹이 된다
        for lang in ("en", "ko", "ja"):
            t = self.target("Krankenhaus", lang)
            self.assertEqual([g["de"] for g in t["alignment"]], [[0, 1]], lang)

    def test_modifier_never_pairs_with_head_position(self):
        # Staub(수식어)가 핵심어 자리의 '기'(機)와 짝지어지던 문제
        ko = self.target("Staubsauger", "ko")
        words = [m["surface"] for m in ko["decomposition"]["morphemes"]]
        for g in ko["alignment"]:
            if g["de"] == [0] and g["target"]:
                self.assertNotIn("기", [words[i] for i in g["target"]])
        en = self.target("Staubsauger", "en")
        self.assertFalse(any(g["de"] == [0] and g["target"] for g in en["alignment"]))  # cleaner 와도 억지로 짝짓지 않는다

    def test_head_pairs_with_head(self):
        ko = self.target("Kugelschreiber", "ko")
        self.assertTrue(any(g["de"] == [1, 2] and g["target"] == [1] for g in ko["alignment"]))  # Schreiber ~ 펜


class GlossTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from pipeline import analyze

        cls.analyze = staticmethod(analyze)
        cls.tr = GtxTranslator()

    def glosses(self, word):
        a = self.analyze(word, self.tr)
        return {m["lemma"]: m["gloss"] for m in a["de"]["morphemes"]}

    def test_picks_common_sense_not_first_translator_hit(self):
        g = self.glosses("Kugelschreiber")
        self.assertEqual(g["Kugel"], "ball")  # 번역기 단독 조회는 bullet
        self.assertEqual(g["schreiben"], "write")

    def test_noun_part(self):
        self.assertEqual(self.glosses("Staubsauger")["Staub"], "dust")

    def test_particles_use_curated_table(self):
        # Ein 을 번역기에 물으면 'A' (→ 한국어 '라') 가 나온다
        g = self.glosses("Eingang")
        self.assertEqual(g["Ein"], "in / into")

    def test_glosses_are_english_except_grammar_suffixes(self):
        a = self.analyze("Kugelschreiber", self.tr)
        suffix = next(m for m in a["de"]["morphemes"] if m["role"] == "suffix")
        self.assertEqual(suffix["gloss"], "~하는 것·사람")
        for t in a["targets"]:
            for m in t["decomposition"]["morphemes"]:
                self.assertFalse(any("가" <= ch <= "힣" for ch in m["gloss"]) and m["role"] != "suffix", (t["lang"], m))


class TranslatorParseTests(unittest.TestCase):
    """번역기 응답 해석 (오프라인)."""

    def test_pos_groups_and_flat_candidates(self):
        data = [
            [["A", "Ein", None]],  # 문장 번역 결과
            [["noun", ["gear", "passage"]], ["verb", ["go"]]],  # 사전 항목(품사별)
            None, None, None,
            [["Ein", None, [["One", 1]]]],  # 대체 번역
        ]
        flat, groups = GtxTranslator._parse(data)
        self.assertEqual(flat, ["A", "gear", "passage", "go", "One"])  # 중복 제거, 대표 번역이 맨 앞
        self.assertEqual(groups, {"noun": ["gear", "passage"], "verb": ["go"]})

    def test_missing_sections(self):
        flat, groups = GtxTranslator._parse([[["x", "y", None]], None])
        self.assertEqual((flat, groups), (["x"], {}))


class PosGlossTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from pipeline import analyze

        cls.analyze = staticmethod(analyze)
        cls.tr = GtxTranslator()

    def gloss(self, word, lemma):
        a = self.analyze(word, self.tr)
        return next(m["gloss"] for m in a["de"]["morphemes"] if m["lemma"] == lemma)

    def test_noun_part_uses_noun_entries(self):
        # 번역기의 문장 번역(예: 'A', 'Um')이 아니라 같은 품사의 사전 항목에서 고른다
        self.assertEqual(self.gloss("Handschuh", "Schuh"), "shoe")
        self.assertEqual(self.gloss("Regenschirm", "Schirm"), "umbrella")

    def test_adjective_part(self):
        self.assertEqual(self.gloss("Krankenhaus", "krank"), "sick")


class UnsplittableWordTests(unittest.TestCase):
    """더 쪼갤 수 없는 단일 단어는 번역기를 부르지 않고 멈춘다."""

    class ExplodingTranslator:
        def lookup(self, *a, **k):
            raise AssertionError("번역기를 부르면 안 된다")

        lookup_pos = lookup

    def run_word(self, word):
        from pipeline import analyze

        return analyze(word, self.ExplodingTranslator())

    def test_simplex_words_stop_early(self):
        for w in ("Zeitung", "Haus", "Bibliothek", "Schmetterling", "Lehrer"):
            a = self.run_word(w)
            self.assertEqual(len(a["de"]["morphemes"]), 1, w)
            self.assertTrue(all(not t["found"] for t in a["targets"]), w)

    def test_derived_word_is_not_treated_as_simplex(self):
        # Gesundheit = gesund + -heit : 쪼갤 수 있으므로 계속 진행(→ 번역기 호출을 시도한다)
        with self.assertRaises(AssertionError):
            self.run_word("Gesundheit")
