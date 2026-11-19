import pytest

from app import catalog, engine, rules, tz_builder
from app.llm import HeuristicExtractor
from app.schemas import CustomRequest, Extraction, PageOp, TZState

X = HeuristicExtractor()


def say(state, text, ex=X):
    return engine.process_turn(state, text, ex)


def new():
    s = TZState()
    engine.start(s)
    return s


SKIP = "Developer ilə dəqiqləşdirəcəm"
LATER = "Bütün səhifələrin məzmununu sonra göndərəcəm"
NEW_SITE = "Yeni sayt (sıfırdan)"


def skip_to(s, target):
    """Hədəf slota çatana qədər hər keçilə bilən sualı «developer ilə dəqiqləşdirəcəm» ilə keç."""
    for _ in range(40):
        if s.pending_slot == target:
            return
        say(s, LATER if s.pending_slot.startswith("page:") else SKIP)
    raise AssertionError(f"{target} slotuna çatılmadı, indi: {s.pending_slot}")


def to_design(s):
    """Korporativ sayt seçildikdən sonra dizayn sualına qədər (mövcud sayt, struktur, səhifə məzmunu, dil, idarəetmə...)."""
    for t in ("Atlas", "Məqsəd", "Hər ikisi", NEW_SITE, "Struktur uyğundur", LATER, "AZ", "Özüm idarə edəcəm"):
        say(s, t)
    skip_to(s, "field:design_style")


def test_start_asks_site_type():
    s = TZState()
    r = engine.start(s)
    assert s.pending_slot == "field:site_type"
    assert "Korporativ sayt" in r.chips
    assert "devices" in s.fields and s.fields["devices"].source == "template"


def test_corporate_happy_path_reaches_final():
    s = new()
    say(s, "Korporativ sayt")
    assert rules.has_module(s, "contact_form") and len(s.structure.pages) == 4
    say(s, "Atlas Logistika")
    say(s, "Yük daşımalarını tanıtmaq və sorğu toplamaq")
    say(s, "Şirkətlər (B2B)")
    assert s.pending_slot == "field:existing_site"
    say(s, "Mövcud saytın yenidən hazırlanması")
    assert s.pending_slot == "field:existing_site_url"  # yalnız redesign olanda soruşulur
    say(s, "https://atlas-kohne.az")
    r = say(s, "Struktur uyğundur")
    assert s.structure_confirmed and r.show_tree is False
    assert s.pending_slot.startswith("page:")  # hər səhifənin məzmunu soruşulur
    say(s, "Şirkətin təqdimatı, 3 şəkil və slayder mətnləri")
    say(s, "Developer ilə dəqiqləşdirəcəm")
    say(s, LATER)
    assert s.pending_slot == "field:languages"
    say(s, "AZ + EN")
    say(s, "Özüm idarə edəcəm")
    say(s, "Domen və hostinq var")
    assert s.pending_slot == "field:domain_name"
    say(s, "atlas.az")
    say(s, "Lazım deyil")  # seo_analytics
    assert s.pending_slot == "field:design_style"
    say(s, "Bilmirəm")  # design_style: təxmin yoxdur, izah + yenidən sual
    assert "design_style" not in s.fields and s.pending_slot == "field:design_style"
    say(s, "Developer ilə dəqiqləşdirəcəm")  # açıq sual kimi qeyd olunur
    assert "design_style" in s.skipped and "design_style" not in s.fields
    say(s, "Hər ikisi var")
    assert s.pending_slot == "field:brand_logo"  # "var" dedikdə loqo soruşulur
    say(s, "Loqonu sonra göndərəcəm")
    assert s.pending_slot == "field:brand_colors"
    say(s, "#0A3D91")
    assert s.fields["brand_colors"].value == "#0A3D91" and "brand_logo" in s.skipped
    say(s, "Nümunə yoxdur")
    assert s.pending_slot == "field:reference_screenshots"
    say(s, "Skrinşotum yoxdur")
    assert s.fields["reference_screenshots"].value == "Yoxdur"
    say(s, "Rəqib göstərmirəm")
    say(s, "+994 12 345 67 89, Bakı, Nizami küç. 10, 09:00-18:00")
    assert s.pending_slot == "field:social_links"  # kontakt səhifəsində social_links modulu var
    say(s, "Sosial şəbəkəm yoxdur")
    assert s.pending_slot == "field:map_location"
    say(s, "Bakı, Nizami küç. 10")
    say(s, "info@atlas.az")
    say(s, "2-3 ay ərzində")
    say(s, "Əliyev Ali, direktor")
    say(s, "2 raund")
    say(s, "Özüm təqdim edəcəm")
    r = say(s, "3000-8000 AZN")
    assert r.ready_for_summary and rules.next_slot(s) == "final"
    tz = tz_builder.build_tz(s)
    assert tz["ready"] and tz["progress"] == 100
    assert all(sec["status"] == "completed" for sec in tz["sections"])
    assert tz["budget"]["cost_min"] > 0 and tz["budget"]["weeks"] >= 1
    # yeni cavablar TZ-yə düşür
    vals = " | ".join(str(i["value"]) for sec in tz["sections"] for i in sec["items"])
    for needle in ("atlas.az", "atlas-kohne.az", "Əliyev Ali, direktor", "2 raund", "Nizami küç. 10", "Şirkətin təqdimatı"):
        assert needle in vals, needle
    # açıq suallar: dizayn, loqo və iki səhifənin məzmunu
    assert sum("məzmunu" in c for c in tz["clarifications"]) == 3
    # analitika "Lazım deyil" dedi: standart analitika tələbi yazılmır
    assert "Yandex" not in vals and "Google Analytics" not in vals


def test_unknown_is_never_guessed():
    s = new()
    for t in ("Korporativ sayt", "Atlas", "Məqsəd"):
        say(s, t)
    assert s.pending_slot == "field:audience"
    r = say(s, "Bilmirəm")
    assert "audience" not in s.fields and "audience" not in s.skipped
    assert s.pending_slot == "field:audience" and "təxmin etmirəm" in r.reply
    say(s, "bilmirəm")  # ikinci dəfə: açıq sual
    assert "audience" in s.skipped and "audience" not in s.fields
    tz = tz_builder.build_tz(s)
    assert any("Hədəf auditoriya" in c for c in tz["clarifications"])
    aud = next(i for sec in tz["sections"] for i in sec["items"] if i["label"] == "Hədəf auditoriya")
    assert aud["source"] == "open"


def test_core_fields_cannot_be_skipped_and_no_skip_chip():
    s = new()
    r = say(s, "Korporativ sayt")
    assert s.pending_slot == "field:company_name" and r.chips == []
    for _ in range(3):
        say(s, "Bilmirəm")
    assert "company_name" not in s.skipped and s.pending_slot == "field:company_name"


def test_contradiction_with_user_values():
    s = new()
    say(s, "Korporativ sayt")
    say(s, "Onlayn mağaza")
    rules.set_field(s, "languages", "AZ + EN + RU", "user")
    rules.set_field(s, "budget_range", "1000 AZN-ə qədər", "user")
    rules.ensure_requirements(s)
    warns = rules.check_contradictions(s)
    assert any("büdcənizdən" in w for w in warns)


def test_brand_flow_branches():
    s = new()
    say(s, "Korporativ sayt")
    to_design(s)
    say(s, "Minimalist və korporativ")
    say(s, "Yalnız rəng var")  # loqo soruşulmur, birbaşa rəng
    assert s.pending_slot == "field:brand_colors"
    s2 = new()
    say(s2, "Korporativ sayt")
    to_design(s2)
    say(s2, "Minimalist və korporativ")
    r = say(s2, "Heç biri yoxdur")  # nə loqo, nə rəng soruşulur
    assert s2.pending_slot == "field:reference_sites" and r.widget is None
    s3 = new()
    say(s3, "Korporativ sayt")
    to_design(s3)
    say(s3, "Minimalist və korporativ")
    r = say(s3, "Yalnız loqo var")
    assert s3.pending_slot == "field:brand_logo" and r.widget == "logo"
    r = say(s3, "salam")  # mətn loqo əvəz etmir
    assert "brand_logo" not in s3.fields and r.widget == "logo"
    rules.set_field(s3, "brand_logo", "logo.png", "user")
    r = engine.after_files(s3, ["logo.png"])
    assert s3.pending_slot == "field:reference_sites"  # yalnız loqo: rəng soruşulmur


def test_structure_add_known_module_and_unknown_becomes_custom():
    s = new()
    say(s, "Korporativ sayt")
    for t in ("Atlas", "Məqsəd", "Hər ikisi", NEW_SITE):
        say(s, t)
    assert s.pending_slot == "structure"
    say(s, "Bloq / Xəbərlər əlavə et")
    assert rules.has_module(s, "blog") and not s.structure_confirmed
    r = say(s, "1C mühasibatlıq ilə sinxronizasiya lazımdır")  # kataloqda yox
    assert len(s.custom_items) == 1
    assert s.pending_slot.startswith("custom:")
    assert "1C" in r.reply
    # custom saatı uydurulmur
    est = rules.estimate(s)
    assert est["has_custom"] and est["custom_rows"]
    for _ in range(4):
        say(s, "Bilmirəm, developer qiymətləndirsin")
    assert s.pending_slot == "structure"
    tz = tz_builder.build_tz(s)
    assert any("əl ilə qiymətləndirilməlidir" in c for c in tz["clarifications"])


def test_dependency_rules_payment_and_languages():
    s = new()
    say(s, "Onlayn mağaza")
    assert rules.has_module(s, "payment") and rules.has_module(s, "cart")
    d = rules.derive(s)
    assert any("HTTPS məcburidir" in x for x in d["security"])
    assert d["platform"].startswith("Laravel")
    assert rules.applicable_fields(s).count("payment_provider") == 1
    rules.set_field(s, "languages", "AZ + EN + RU", "user")
    rules.ensure_requirements(s)
    assert rules.has_module(s, "multilingual")


def test_contradiction_budget_vs_scope():
    s = new()
    say(s, "Onlayn mağaza")
    rules.set_field(s, "languages", "AZ + EN + RU", "user")
    rules.set_field(s, "budget_range", "1000 AZN-ə qədər", "user")
    rules.ensure_requirements(s)
    warns = rules.check_contradictions(s)
    assert any("büdcənizdən" in w for w in warns)


def test_unclear_answer_does_not_invent_value():
    s = new()
    say(s, "Korporativ sayt")
    for t in ("Atlas", "Məqsəd"):
        say(s, t)
    r = say(s, "hmm")  # audience: allow_other var -> "hmm" qəbul olunur; başqa sahəni yoxlayaq
    s2 = new()
    say(s2, "Korporativ sayt")
    for t in ("Atlas", "Məqsəd", "Hər ikisi", NEW_SITE, "Struktur uyğundur", LATER):
        say(s2, t)
    assert s2.pending_slot == "field:languages"
    say(s2, "bilmirəm nə olar")  # təxmin yoxdur: yenidən soruşulur
    assert "languages" not in s2.fields and s2.pending_slot == "field:languages"


def test_extraction_cannot_inject_unknown_fields_or_bad_email():
    s = new()
    ext = Extraction(fields={"hacked": "x", "site_type": "Korporativ sayt"})
    engine.apply_extraction(s, "field:site_type", "x", ext)
    assert "hacked" not in s.fields and "site_type" in s.fields
    rules.set_field(s, "company_name", "A", "user")
    assert rules.coerce_field("contact_email", "not-an-email") is None


def test_page_ops_via_ui_delete_removes_custom_item():
    s = new()
    say(s, "Korporativ sayt")
    engine.apply_page_ops(s, [__import__("app.schemas", fromlist=["PageOp"]).PageOp(op="add", name="3D konfiqurator")])
    assert len(s.custom_items) == 1
    engine.apply_page_ops(s, [__import__("app.schemas", fromlist=["PageOp"]).PageOp(op="remove", name="3D konfiqurator")])
    assert not s.custom_items
    assert not [m for m in rules.all_modules(s) if m.kind == "custom"]


class FakeLLM:
    def __init__(self, ext):
        self.ext = ext

    def extract(self, ctx):
        return self.ext


def test_llm_extracted_multi_field_and_custom():
    s = new()
    fake = FakeLLM(Extraction(ack="Əla!", fields={"site_type": "Onlayn mağaza", "company_name": "Moda.az"},
                              custom_requests=[CustomRequest(title="3D konfiqurator", description="Mebel üçün")]))
    r = engine.process_turn(s, "Moda.az adlı mağaza istəyirəm, 3D konfiqurator da olsun", fake)
    assert s.fields["company_name"].value == "Moda.az" and s.fields["company_name"].source == "user"
    assert len(s.custom_items) == 1 and r.reply.startswith("Əla!")


# ---------- yeni suallar ----------
def to_structure_done(s, site="Korporativ sayt"):
    say(s, site)
    for t in ("Atlas", "Məqsəd", "Hər ikisi", NEW_SITE, "Struktur uyğundur"):
        say(s, t)


def test_page_content_one_question_per_page_with_open_and_all_later():
    s = new()
    to_structure_done(s)
    names = [p.name for p in s.structure.pages]
    assert len(names) == 4 and s.pending_slot.startswith("page:")
    r = say(s, "Bilmirəm")  # təxmin yox: izah + yenidən sual
    assert "təxmin etmirəm" in r.reply and s.structure.pages[0].content_status == "pending"
    say(s, "bilmirəm")  # ikinci dəfə: açıq sual
    assert s.structure.pages[0].content_status == "open" and s.structure.pages[0].content == ""
    r = say(s, "Komanda şəkilləri və CV-lər")
    assert s.structure.pages[1].content_status == "answered" and "Komanda" in s.structure.pages[1].content
    assert LATER in r.chips and SKIP in r.chips
    say(s, LATER)
    assert [p.content_status for p in s.structure.pages] == ["open", "answered", "open", "open"]
    assert s.pending_slot == "field:languages"
    tz = tz_builder.build_tz(s)
    assert sum("məzmunu" in c for c in tz["clarifications"]) == 3
    page_row = next(i for i in tz["sections"][2]["items"] if i["label"] == names[0])
    assert page_row["source"] == "open"


def test_page_content_added_page_is_asked_and_rename_keeps_content():
    s = new()
    to_structure_done(s)
    say(s, "Ana səhifə mətni")
    say(s, LATER)
    engine.apply_page_ops(s, [PageOp(op="rename", name="Haqqımızda", new_name="Şirkət haqqında")])
    assert next(p for p in s.structure.pages if p.name == "Şirkət haqqında").content_status == "open"
    assert next(p for p in s.structure.pages if p.name == "Ana səhifə").content == "Ana səhifə mətni"
    engine.apply_page_ops(s, [PageOp(op="add", name="Qalereya")])
    engine.after_edit(s, ["added"])
    assert s.pending_slot == "structure"  # struktur dəyişdi: əvvəl yenidən təsdiq
    say(s, "Struktur uyğundur")
    assert s.pending_slot.startswith("page:")  # yalnız yeni səhifənin məzmunu soruşulur
    assert rules.find_page_by_id(s, s.pending_slot.split(":", 1)[1]).name == "Qalereya"
    assert "Qalereya" in s.structure.pages[-1].name and "Qalereya" in engine.question_for(s.pending_slot, s)[0]


def test_page_content_not_set_by_llm_skip_rest():
    from app import llm
    ext = llm.parse_extraction('{"skip_rest": true, "skip": true, "fields": {}}')
    assert ext.skip_rest is False and ext.skip is False


def test_redesign_url_only_for_redesign_and_adds_requirement():
    s = new()
    for t in ("Korporativ sayt", "Atlas", "Məqsəd", "Hər ikisi", NEW_SITE):
        say(s, t)
    assert "existing_site_url" not in rules.applicable_fields(s) and s.pending_slot == "structure"
    s2 = new()
    for t in ("Korporativ sayt", "Atlas", "Məqsəd", "Hər ikisi", "redesign"):  # sərbəst mətn də qəbul olunur
        say(s2, t)
    assert s2.pending_slot == "field:existing_site_url"
    say(s2, "https://old.atlas.az")
    assert s2.fields["existing_site_url"].value == "https://old.atlas.az"
    assert any("301" in x for x in rules.derive(s2)["tech"])
    assert not any("301" in x for x in rules.derive(s)["tech"])


def test_domain_hosting_feeds_technical_section():
    s = new()
    say(s, "Korporativ sayt")
    rules.set_field(s, "domain_hosting", "Heç biri yoxdur", "user")
    assert "domain_name" not in rules.applicable_fields(s)
    assert any("adının qeydiyyatını" in x for x in rules.derive(s)["tech"])
    rules.set_field(s, "domain_hosting", "Yalnız domen var", "user")
    assert "domain_name" in rules.applicable_fields(s)
    tz = tz_builder.build_tz(s)
    sec5 = next(x for x in tz["sections"] if x["number"] == 5)
    assert any(i["label"] == "Domen və hostinq" for i in sec5["items"])
    assert any("DNS" in str(i["value"]) for i in sec5["items"] if i.get("req"))


def test_analytics_requirement_follows_answer():
    s = new()
    say(s, "Korporativ sayt")

    def funcs():
        return " | ".join(rules.derive(s)["functional"])
    assert "Yandex" in funcs()  # sual hələ verilməyib: əvvəlki standart
    rules.set_field(s, "seo_analytics", "Google Analytics + Search Console", "user")
    assert "Google Analytics qoşulması" in funcs() and "Search Console" in funcs() and "Yandex" not in funcs()
    rules.set_field(s, "seo_analytics", "Yalnız Search Console", "user")
    assert "Search Console" in funcs() and "Google Analytics qoşulması" not in funcs()
    rules.set_field(s, "seo_analytics", "Lazım deyil", "user")
    assert "Analytics" not in funcs() and "Search Console" not in funcs()
    rules.set_field(s, "seo_analytics", "Meta Pixel", "user")  # sərbəst cavab olduğu kimi yazılır
    assert "Meta Pixel" in funcs()
    s.fields.pop("seo_analytics")
    rules.mark_open(s, "seo_analytics")  # bilmir: heç nə uydurulmur, açıq sual
    assert "Yandex" not in funcs() and "Analytics" not in funcs()
    assert any("SEO və analitika" in c for c in tz_builder.build_tz(s)["clarifications"])


def test_social_and_map_questions_only_when_module_present():
    s = new()
    say(s, "Onlayn mağaza")  # şablonda map var, social_links yoxdur
    ap = rules.applicable_fields(s)
    assert "map_location" in ap and "social_links" not in ap and "contact_details" in ap
    engine.apply_page_ops(s, [PageOp(op="add_module", name="Əlaqə", module_types=["social_links"])])
    assert "social_links" in rules.applicable_fields(s)


def test_competitors_approver_and_revision_rounds_are_optional_skippable():
    for fid in ("competitors", "approver", "revision_rounds", "contact_details", "domain_hosting", "seo_analytics"):
        f = catalog.field(fid)
        assert f and not f.get("required") and rules.is_skippable(fid)
    r = rules.coerce_field("revision_rounds", "3")
    assert r == "3 raund"
    assert rules.coerce_field("revision_rounds", "limitsiz") == "limitsiz"  # allow_other


# ---------- LLM: bir cavabdan bir neçə sahə, «niyə soruşuruq», provayder izi ----------
def test_long_answer_fills_several_fields_and_skips_their_questions():
    s = new()
    fake = FakeLLM(Extraction(ack="Əla!", fields={"site_type": "Onlayn mağaza", "company_name": "Kafel.az",
                                                  "languages": "AZ + EN", "audience": "Şirkətlər (B2B)"}))
    r = engine.process_turn(s, "Kafel satırıq, kataloq lazımdır, iki dildə, şirkətlərə", fake)
    assert s.fields["languages"].value == "AZ + EN" and s.fields["audience"].value == "Şirkətlər (B2B)"
    assert all(s.fields[f].source == "user" for f in ("site_type", "company_name", "languages", "audience"))
    # bot artıq cavablanmış sualları təkrar soruşmur
    assert s.pending_slot == "field:purpose"
    assert "Əlavə" in r.reply or "qeyd etdim" in r.reply
    assert "Kafel.az" in r.reply and "AZ + EN" in r.reply


def test_extra_fields_not_applicable_yet_are_dropped_not_stored():
    s = new()
    say(s, "Korporativ sayt")
    # ödəniş və CV sahələri yalnız həmin modul strukturda varsa tətbiq olunur (korporativ sayt şablonunda yoxdur)
    assert not rules.has_module(s, "payment") and not rules.has_module(s, "career")
    fake = FakeLLM(Extraction(fields={"company_name": "Atlas", "payment_provider": "Yerli bank kartları",
                                      "cv_details": "PDF, 5 MB", "devices": "iPhone"}))
    engine.process_turn(s, "Atlas, kartla ödəniş, CV formu", fake)
    assert "payment_provider" not in s.fields and "cv_details" not in s.fields
    assert s.fields["devices"].source == "template"
    assert s.fields["company_name"].value == "Atlas"


def test_dependent_extra_fields_follow_flow_order():
    s = new()
    to_design_state = new()
    for t in ("Korporativ sayt", "Atlas", "Məqsəd", "Hər ikisi"):
        say(to_design_state, t)
    fake = FakeLLM(Extraction(fields={"existing_site_url": "https://atlas.az", "existing_site": "Mövcud saytın yenidən hazırlanması"}))
    engine.process_turn(to_design_state, "Köhnə saytımız https://atlas.az, yenidən hazırlayın", fake)
    assert to_design_state.fields["existing_site_url"].value == "https://atlas.az"
    # yalnız URL (redesign cavabı olmadan) tətbiq olunmur
    s2 = new()
    for t in ("Korporativ sayt", "Atlas", "Məqsəd", "Hər ikisi"):
        say(s2, t)
    engine.process_turn(s2, "https://atlas.az", FakeLLM(Extraction(fields={"existing_site_url": "https://atlas.az"})))
    assert "existing_site_url" not in s2.fields


def test_text_slot_not_filled_with_whole_sentence_when_llm_extracts_other_fields():
    s = new()
    say(s, "Korporativ sayt")
    assert s.pending_slot == "field:company_name"
    fake = FakeLLM(Extraction(fields={"languages": "AZ + EN"}))
    engine.process_turn(s, "iki dildə olsun, adı sonra deyərəm", fake)
    assert "company_name" not in s.fields and s.fields["languages"].value == "AZ + EN"
    assert s.pending_slot == "field:company_name"


def test_llm_cannot_set_engine_only_keys():
    from app.llm import parse_extraction
    e = parse_extraction('{"fields": {"company_name": "A"}, "skip": true, "skip_rest": true, "noted": ["x"]}')
    assert not e.skip and not e.skip_rest and e.noted == []


def test_every_question_has_why_line_in_all_languages():
    from app import i18n
    for lang in ("az", "en", "ru"):
        i18n.set_lang(lang)
        s = TZState(language=lang)
        r = engine.start(s)
        assert r.why
        for fid, f in catalog.fields().items():
            if f.get("ask", True) is False:
                continue
            assert f.get("why"), (lang, fid)
        for slot in ("structure", "page:x", "custom:a:who_uses"):
            assert engine.why_for(slot, s), (lang, slot)
    i18n.set_lang("az")


def test_why_is_returned_with_each_turn():
    s = new()
    r = say(s, "Korporativ sayt")
    assert r.why and "ad" in r.why.lower()


def test_prompt_v3_lists_unfilled_fields_and_example_ids_exist():
    from app import llm
    s = new()
    say(s, "Korporativ sayt")
    p = llm.build_system_prompt(llm.Ctx(s, "x", s.pending_slot, "?"))
    assert "HƏLƏ DOLDURULMAMIŞ" in p and "company_name" in p and "{{" not in p
    assert "product_catalog" in p and catalog.module("product_catalog")
