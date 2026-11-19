"""Çoxdillilik (AZ/EN/RU): cari dil (contextvar), mətn lüğəti və YAML lokallaşdırması.

Kod mətnləri S lüğətindədir; YAML fayllarında tərcümə olunan sahələr {az:..., en:..., ru:...} formasındadır.
Dil sessiyanın dilidir (TZState.language) və söhbət boyu dəyişmir."""
from __future__ import annotations

from contextvars import ContextVar
from typing import Any

LANGS = ("az", "en", "ru")
LANG_NAMES = {"az": "Azərbaycan", "en": "ingilis", "ru": "rus"}
_lang: ContextVar[str] = ContextVar("lang", default="az")


def set_lang(lang: str) -> None:
    _lang.set(lang if lang in LANGS else "az")


def cur() -> str:
    return _lang.get()


def loc(obj: Any, lang: str) -> Any:
    """YAML ağacında {az,en,ru} lüğətlərini seçilmiş dilin mətninə çevirir."""
    if isinstance(obj, dict):
        if "az" in obj and set(obj) <= set(LANGS):
            return obj.get(lang) or obj["az"]
        return {k: loc(v, lang) for k, v in obj.items()}
    if isinstance(obj, list):
        return [loc(v, lang) for v in obj]
    return obj


def t(key: str, lang: str | None = None, **kw: Any) -> Any:
    entry = S[key]
    val = entry.get(lang or cur()) or entry["az"]
    if kw and isinstance(val, str):
        return val.format(**kw)
    return val


S: dict[str, dict[str, Any]] = {
    # ---------- engine ----------
    "greeting": {
        "az": "Salam! Saytınız üçün texniki tapşırığı (TZ) sadə suallarla birlikdə hazırlayacağıq. "
              "Texniki bilik tələb olunmur. Mən heç nəyi təxmin etmirəm: TZ-də yalnız sizin dediyiniz məlumat olacaq. "
              "Nəyisə hələ bilmirsinizsə, bunu «açıq sual» kimi qeyd edəcəyəm.\n\n",
        "en": "Hello! We will prepare the technical specification (TZ) for your website together, with simple questions. "
              "No technical knowledge is needed. I do not guess anything: the TZ will contain only what you tell me. "
              "If you do not know something yet, I will record it as an \"open question\".\n\n",
        "ru": "Здравствуйте! Мы вместе подготовим техническое задание (ТЗ) для вашего сайта простыми вопросами. "
              "Технические знания не нужны. Я ничего не придумываю: в ТЗ будет только то, что вы скажете. "
              "Если чего-то пока не знаете, я отмечу это как «открытый вопрос».\n\n",
    },
    "final_q": {
        "az": "Bütün əsas məlumatlar toplandı. İndi xülasəyə baxıb təsdiq edə bilərsiniz. "
              "Nəyisə dəyişmək istəyirsinizsə, elə indi yazın.",
        "en": "All the main information has been collected. You can now review the summary and confirm it. "
              "If you want to change anything, write it now.",
        "ru": "Вся основная информация собрана. Теперь вы можете посмотреть сводку и подтвердить её. "
              "Если хотите что-то изменить, напишите это сейчас.",
    },
    "chip_summary": {"az": "Xülasəyə bax", "en": "View summary", "ru": "Посмотреть сводку"},
    "struct_again": {
        "az": "Başqa dəyişiklik varmı? Kartdakı düymələrdən və ya aşağıdakı yazı xanasından istifadə edə bilərsiniz. "
              "Yoxdursa «{ok}» seçin.",
        "en": "Any other changes? You can use the buttons on the card or the text box below it. "
              "If not, choose «{ok}».",
        "ru": "Есть другие изменения? Можно использовать кнопки на карточке или поле для текста под ней. "
              "Если нет, выберите «{ok}».",
    },
    "custom_intro": {
        "az": "**«{title}»** tələbini dəqiqləşdirək (bu hissə hazır kataloqda yoxdur, ona görə developer ayrıca qiymətləndirəcək). ",
        "en": "Let's clarify the requirement **«{title}»** (this part is not in our ready catalog, so the developer will estimate it separately). ",
        "ru": "Давайте уточним требование **«{title}»** (его нет в нашем готовом каталоге, поэтому разработчик оценит его отдельно). ",
    },
    "add_chip": {"az": "{title} əlavə et", "en": "Add {title}", "ru": "Добавить: {title}"},
    "note_page_added": {"az": "«{name}» səhifəsi əlavə olundu", "en": "page «{name}» added", "ru": "страница «{name}» добавлена"},
    "note_page_removed": {"az": "«{name}» səhifəsi çıxarıldı", "en": "page «{name}» removed", "ru": "страница «{name}» удалена"},
    "note_renamed": {"az": "«{old}» → «{new}»", "en": "«{old}» → «{new}»", "ru": "«{old}» → «{new}»"},
    "note_page_edited": {"az": "«{name}» səhifəsi yeniləndi", "en": "page «{name}» updated", "ru": "страница «{name}» обновлена"},
    "note_module_added": {"az": "{title} əlavə olundu", "en": "{title} added", "ru": "{title} добавлен"},
    "note_module_removed": {"az": "Modul çıxarıldı", "en": "Module removed", "ru": "Модуль удалён"},
    "ack_struct": {"az": "Strukturu yenilədim.", "en": "I updated the structure.", "ru": "Я обновил структуру."},
    "marked_open": {
        "az": "Bu hissəni «açıq sual» kimi qeyd etdim: heç nə təxmin etmədim, developer sizinlə dəqiqləşdirəcək.",
        "en": "I noted this as an \"open question\": I did not guess anything, the developer will clarify it with you.",
        "ru": "Я отметил это как «открытый вопрос»: ничего не придумывал, разработчик уточнит это с вами.",
    },
    "dont_guess": {
        "az": "Problem deyil, amma mən bunu təxmin etmirəm. Varianta baxın və uyğun olanı seçin ya da öz sözlərinizlə yazın. "
              "Hələ bilmirsinizsə, «{skip}» seçin.",
        "en": "No problem, but I do not guess this. Have a look at the options and pick one or write it in your own words. "
              "If you do not know yet, choose «{skip}».",
        "ru": "Ничего страшного, но я не буду это придумывать. Посмотрите варианты и выберите подходящий или напишите своими словами. "
              "Если пока не знаете, выберите «{skip}».",
    },
    "dont_guess_required": {
        "az": "Bu məlumat olmadan TZ yaza bilmərik, mən də təxmin etmirəm. Qısaca da olsa yazın.",
        "en": "We cannot write the TZ without this, and I do not guess. Please write it, even briefly.",
        "ru": "Без этой информации ТЗ не написать, а я ничего не придумываю. Напишите хотя бы коротко.",
    },
    "dont_guess_structure": {
        "az": "Strukturu sizin əvəzinizə təsdiqləmirəm. Uyğun gəlməyən hissəni yazın (çıxarmaq/əlavə etmək) və ya təsdiq edin.",
        "en": "I will not confirm the structure for you. Tell me what does not fit (remove/add) or confirm it.",
        "ru": "Я не буду подтверждать структуру за вас. Напишите, что не подходит (убрать/добавить), или подтвердите.",
    },
    "logo_received": {
        "az": "Loqonuz qəbul edildi: {name}.",
        "en": "Your logo was received: {name}.",
        "ru": "Ваш логотип получен: {name}.",
    },
    "not_understood": {
        "az": "Cavabınızı tam başa düşə bilmədim. Zəhmət olmasa seçimlərdən birini seçin və ya başqa sözlərlə yazın.",
        "en": "I could not fully understand your answer. Please choose one of the options or rephrase it.",
        "ru": "Я не совсем понял ваш ответ. Пожалуйста, выберите один из вариантов или напишите другими словами.",
    },
    "final_more": {
        "az": "Əlavə düzəliş üçün konkret yazın, məsələn: «Bloq əlavə et» və ya «Dilləri AZ + EN et». Hazırsınızsa xülasəyə keçin.",
        "en": "For further changes, write something specific, for example: «Add a blog» or «Set the languages to AZ + EN». If you are ready, go to the summary.",
        "ru": "Для дополнительных правок напишите конкретно, например: «Добавь блог» или «Сделай языки AZ + EN». Если готовы, переходите к сводке.",
    },
    "after_edit_ok": {"az": "Strukturu yenilədim: {notes}.", "en": "I updated the structure: {notes}.", "ru": "Я обновил структуру: {notes}."},
    "answers_new_questions": {"az": "Düzəlişlərinizi yadda saxladım. Cavablarınıza görə bir neçə yeni sual əlavə olundu.", "en": "I saved your changes. A few new questions came up because of your answers.", "ru": "Я сохранил ваши изменения. Из-за ваших ответов появилось несколько новых вопросов."},
    "after_edit_none": {"az": "Struktur dəyişməyib.", "en": "The structure has not changed.", "ru": "Структура не изменилась."},
    "also_noted": {
        "az": "Cavabınızdan bunları da qeyd etdim (səhv varsa yazın, düzəldərəm): {items}.",
        "en": "I also noted these from your answer (tell me if anything is wrong and I will fix it): {items}.",
        "ru": "Из вашего ответа я также записал: {items}. Если что-то не так, напишите, и я исправлю.",
    },
    "acks": {
        "az": ["Qeyd etdim.", "Aydındır.", "Başa düşdüm.", "Əla."],
        "en": ["Noted.", "Got it.", "Understood.", "Great."],
        "ru": ["Записал.", "Понятно.", "Принято.", "Отлично."],
    },
    "unspecified": {"az": "Dəqiqləşdirilməyib", "en": "Not specified", "ru": "Не уточнено"},
    "page_content_intro": {
        "az": "Struktur təsdiqləndi. İndi hər səhifənin məzmununu soruşacağam ki, developer nəyin hazırlanacağını bilsin. "
              "Bilmədiyiniz səhifəni «açıq sual» kimi qeyd edə bilərsiniz.\n\n",
        "en": "The structure is confirmed. Now I will ask about the content of each page, so the developer knows what has to be prepared. "
              "You can mark any page you are unsure about as an \"open question\".\n\n",
        "ru": "Структура подтверждена. Теперь я спрошу про контент каждой страницы, чтобы разработчик знал, что нужно подготовить. "
              "Любую страницу, по которой пока не уверены, можно отметить как «открытый вопрос».\n\n",
    },
    "dont_guess_page": {
        "az": "Problem deyil, amma mən səhifənin məzmununu təxmin etmirəm. Qısaca da olsa yazın (məsələn: mətn, şəkil, siyahı) "
              "ya da «{skip}» seçin.",
        "en": "No problem, but I do not guess the page content. Write it briefly (for example: text, photos, a list) "
              "or choose «{skip}».",
        "ru": "Ничего страшного, но я не буду придумывать контент страницы. Напишите хотя бы коротко (например: текст, фото, список) "
              "или выберите «{skip}».",
    },
    # ---------- rules ----------
    "custom_item_desc": {
        "az": "Müştəri standart şablonlara uyğun gəlməyən sayt növü seçib",
        "en": "The customer chose a site type that does not fit the standard templates",
        "ru": "Клиент выбрал тип сайта, не подходящий под стандартные шаблоны",
    },
    "platform_laravel": {
        "az": "Laravel (xüsusi CMS / admin panel)",
        "en": "Laravel (custom CMS / admin panel)",
        "ru": "Laravel (собственная CMS / админ-панель)",
    },
    "why_heavy": {
        "az": "Mürəkkəb funksiyalar (ödəniş, istifadəçi hesabı, rezervasiya və ya xüsusi tələb) olduğu üçün hazır şablon CMS çatmaya bilər.",
        "en": "Because of complex features (payment, user account, booking or a custom requirement), a ready-made template CMS may not be enough.",
        "ru": "Из-за сложных функций (оплата, личный кабинет, бронирование или нестандартное требование) готовой шаблонной CMS может не хватить.",
    },
    "platform_wp": {"az": "WordPress", "en": "WordPress", "ru": "WordPress"},
    "why_wp": {
        "az": "Standart struktur üçün sürətli, idarəsi asan və ucuz seçimdir.",
        "en": "For a standard structure it is a fast, easy-to-manage and affordable choice.",
        "ru": "Для стандартной структуры это быстрый, простой в управлении и недорогой вариант.",
    },
    "module_prefix": {"az": "Modul: {title}", "en": "Module: {title}", "ru": "Модуль: {title}"},
    "page_general": {"az": "Ümumi", "en": "General", "ru": "Общее"},
    "phase_design": {"az": "UI/UX dizayn və prototip", "en": "UI/UX design and prototype", "ru": "UI/UX-дизайн и прототип"},
    "phase_dev": {"az": "Tərtibat (frontend + backend)", "en": "Development (frontend + backend)", "ru": "Разработка (frontend + backend)"},
    "phase_qa": {"az": "Test və düzəlişlər", "en": "Testing and fixes", "ru": "Тестирование и исправления"},
    "phase_setup": {
        "az": "Quraşdırma, yerləşdirmə və idarəetmə",
        "en": "Setup, deployment and management",
        "ru": "Настройка, развёртывание и управление",
    },
    "warn_budget": {
        "az": "Seçdiyiniz funksiyaların təxmini dəyəri (~{lo}–{hi} AZN) büdcənizdən ({budget}) yüksəkdir. "
              "Bəzi modulları çıxarmaq və ya büdcəni yenidən nəzərdən keçirmək olar.",
        "en": "The estimated cost of the selected features (~{lo}–{hi} AZN) is higher than your budget ({budget}). "
              "You can remove some modules or reconsider the budget.",
        "ru": "Примерная стоимость выбранных функций (~{lo}–{hi} AZN) выше вашего бюджета ({budget}). "
              "Можно убрать некоторые модули или пересмотреть бюджет.",
    },
    "warn_budget_short": {
        "az": "Seçdiyiniz funksiyaların təxmini dəyəri (~{lo}–{hi} AZN) büdcənizdən ({budget}) yüksəkdir.",
        "en": "The estimated cost of the selected features (~{lo}–{hi} AZN) is higher than your budget ({budget}).",
        "ru": "Примерная стоимость выбранных функций (~{lo}–{hi} AZN) выше вашего бюджета ({budget}).",
    },
    "warn_deadline": {
        "az": "İstədiyiniz müddət ({deadline}) təxmini icra vaxtından (~{lo}–{hi} həftə) qısadır.",
        "en": "The time you want ({deadline}) is shorter than the estimated delivery time (~{lo}–{hi} weeks).",
        "ru": "Желаемый срок ({deadline}) короче ориентировочного времени выполнения (~{lo}–{hi} нед.).",
    },
    "warn_langs": {
        "az": "3 dilli sayt kiçik büdcə üçün çətin ola bilər: hər dil məzmun və tərcümə işini artırır.",
        "en": "A 3-language site can be hard on a small budget: each language adds content and translation work.",
        "ru": "Трёхъязычный сайт может быть сложным для небольшого бюджета: каждый язык добавляет работу с контентом и переводом.",
    },
    "miss_structure": {"az": "Struktur təsdiqi", "en": "Structure confirmation", "ru": "Подтверждение структуры"},
    "miss_clar": {"az": "Aydınlaşdırma: {title}", "en": "Clarification: {title}", "ru": "Уточнение: {title}"},
    "req_domain_both": {
        "az": "Sayt müştərinin mövcud hostinqinə yerləşdirilir və domen ora yönləndirilir (hostinq və DNS giriş məlumatları müştəridən alınır)",
        "en": "The site is deployed to the client's existing hosting and the domain is pointed to it (hosting and DNS access is provided by the client)",
        "ru": "Сайт размещается на существующем хостинге клиента, домен направляется на него (доступы к хостингу и DNS предоставляет клиент)",
    },
    "req_domain_domain": {
        "az": "Mövcud domen yeni hostinqə yönləndirilir (DNS giriş məlumatları müştəridən alınır); hostinqi developer təşkil edir",
        "en": "The existing domain is pointed to new hosting (DNS access is provided by the client); the developer arranges the hosting",
        "ru": "Существующий домен направляется на новый хостинг (доступ к DNS предоставляет клиент); хостинг организует разработчик",
    },
    "req_domain_hosting": {
        "az": "Domen adını developer qeydiyyatdan keçirir; sayt müştərinin mövcud hostinqinə yerləşdirilir (giriş məlumatları müştəridən alınır)",
        "en": "The developer registers the domain name; the site is deployed to the client's existing hosting (access is provided by the client)",
        "ru": "Доменное имя регистрирует разработчик; сайт размещается на существующем хостинге клиента (доступы предоставляет клиент)",
    },
    "req_domain_none": {
        "az": "Domen adının qeydiyyatını və hostinqin təşkilini developer həyata keçirir",
        "en": "The developer registers the domain name and arranges the hosting",
        "ru": "Регистрацию доменного имени и организацию хостинга выполняет разработчик",
    },
    "req_redesign": {
        "az": "Mövcud saytın yenidən hazırlanması (redesign): köhnə URL-lər üçün 301 yönləndirmə və məzmunun köçürülməsi həcmi developer ilə dəqiqləşdirilir",
        "en": "Redesign of an existing site: 301 redirects for old URLs and the amount of content to migrate are to be clarified with the developer",
        "ru": "Редизайн существующего сайта: 301-редиректы для старых URL и объём переносимого контента уточняются с разработчиком",
    },
    "req_analytics_custom": {
        "az": "Analitika / SEO alətləri (müştərinin istəyi): {value}",
        "en": "Analytics / SEO tools (client's request): {value}",
        "ru": "Инструменты аналитики / SEO (пожелание клиента): {value}",
    },
    # ---------- tz_builder ----------
    "sec1": {"az": "Layihə adı və təsviri", "en": "Project name and description", "ru": "Название и описание проекта"},
    "sec2": {"az": "Ümumi tələblər", "en": "General requirements", "ru": "Общие требования"},
    "sec3": {"az": "Struktur və bölmələr", "en": "Structure and sections", "ru": "Структура и разделы"},
    "sec4": {"az": "Dizayn", "en": "Design", "ru": "Дизайн"},
    "sec5": {"az": "Texniki tələblər", "en": "Technical requirements", "ru": "Технические требования"},
    "sec6": {"az": "Funksional tələblər", "en": "Functional requirements", "ru": "Функциональные требования"},
    "sec7": {"az": "Təhlükəsizlik", "en": "Security", "ru": "Безопасность"},
    "sec8": {"az": "Çatdırılma qrafiki", "en": "Delivery schedule", "ru": "График сдачи"},
    "sec9": {"az": "Əlavələr", "en": "Appendices", "ru": "Приложения"},
    "sec10": {"az": "Büdcə", "en": "Budget", "ru": "Бюджет"},
    "platform_label": {"az": "Platforma (tövsiyə)", "en": "Platform (recommended)", "ru": "Платформа (рекомендация)"},
    "modules_line": {"az": "Modullar: {mods}", "en": "Modules: {mods}", "ru": "Модули: {mods}"},
    "tag_manual": {
        "az": " [əl ilə qiymətləndirilməlidir]",
        "en": " [must be estimated manually]",
        "ru": " [требует ручной оценки]",
    },
    "global_feature": {"az": "Ümumi funksiya", "en": "Global feature", "ru": "Общая функция"},
    "tz_title": {"az": "Texniki Tapşırıq (TZ)", "en": "Technical Specification (TZ)", "ru": "Техническое задание (ТЗ)"},
    "unnamed": {"az": "Adsız layihə", "en": "Untitled project", "ru": "Проект без названия"},
    "req_label": {"az": "Tələb", "en": "Requirement", "ru": "Требование"},
    "est_duration": {"az": "Təxmini icra müddəti", "en": "Estimated duration", "ru": "Ориентировочный срок выполнения"},
    "weeks_range": {"az": "{lo}–{hi} həftə", "en": "{lo}–{hi} weeks", "ru": "{lo}–{hi} нед."},
    "custom_not_included": {
        "az": " (custom tələblər daxil deyil)",
        "en": " (custom requirements not included)",
        "ru": " (нестандартные требования не включены)",
    },
    "work_days": {"az": "{n} iş günü", "en": "{n} working days", "ru": "{n} рабочих дн."},
    "first_demo": {"az": "İlk demo", "en": "First demo", "ru": "Первое демо"},
    "first_demo_val": {
        "az": "Dizayn və prototip mərhələsinin sonunda",
        "en": "At the end of the design and prototype phase",
        "ru": "В конце этапа дизайна и прототипа",
    },
    "brand_note_label": {"az": "Qeyd", "en": "Note", "ru": "Примечание"},
    "brand_note": {
        "az": "Loqo və/və ya korporativ rənglər yoxdur: brend materiallarının hazırlanması bu TZ-yə daxil deyil, ayrıca razılaşdırılmalıdır.",
        "en": "The logo and/or brand colors are missing: creating brand materials is not part of this specification and must be agreed separately.",
        "ru": "Логотипа и/или фирменных цветов нет: разработка брендовых материалов не входит в это ТЗ и согласуется отдельно.",
    },
    "est_total": {"az": "Təxmini ümumi dəyər", "en": "Estimated total cost", "ru": "Ориентировочная общая стоимость"},
    "est_total_val": {
        "az": "{lo}–{hi} AZN, ~{h} saat{extra}",
        "en": "{lo}–{hi} AZN, ~{h} hours{extra}",
        "ru": "{lo}–{hi} AZN, ~{h} ч{extra}",
    },
    "extra_cost": {
        "az": " (custom tələblər daxil deyil, ayrıca qiymətləndirilməlidir)",
        "en": " (custom requirements not included, to be estimated separately)",
        "ru": " (нестандартные требования не включены, оцениваются отдельно)",
    },
    "payment_plan_label": {"az": "Ödəniş planı", "en": "Payment plan", "ru": "План оплаты"},
    "snippet_wait": {"az": "Gözləyir", "en": "Pending", "ru": "Ожидает"},
    "clar_tail": {
        "az": "İcra vaxtı və qiymət əl ilə qiymətləndirilməlidir.",
        "en": "Delivery time and price must be estimated manually.",
        "ru": "Срок и стоимость нужно оценить вручную.",
    },
    "clar_skipped": {
        "az": "«{label}» müştəri tərəfindən dəqiqləşdirilməyib.",
        "en": "«{label}» has not been specified by the customer.",
        "ru": "«{label}» не уточнено клиентом.",
    },
    "content_line": {"az": "Məzmun: {text}", "en": "Content: {text}", "ru": "Контент: {text}"},
    "clar_page_content": {
        "az": "«{name}» səhifəsinin məzmunu müştəri tərəfindən dəqiqləşdirilməyib.",
        "en": "The content of the «{name}» page has not been specified by the customer.",
        "ru": "Контент страницы «{name}» не уточнён клиентом.",
    },
    "refs_value": {
        "az": "{n} skrinşot: {names}",
        "en": "{n} screenshot(s): {names}",
        "ru": "Скриншотов: {n}: {names}",
    },
    "files_received": {
        "az": "Faylınız qəbul edildi: {names}.",
        "en": "Your file was received: {names}.",
        "ru": "Ваш файл получен: {names}.",
    },
    "brand_guide_label": {"az": "Brend bələdçisi (PDF)", "en": "Brand guide (PDF)", "ru": "Брендбук (PDF)"},
    "doc_attachments": {"az": "Yüklənmiş dizayn materialları", "en": "Uploaded design materials", "ru": "Загруженные дизайн-материалы"},
    "logo_saved": {
        "az": "{name} (sessiya ilə birlikdə saxlanılır)",
        "en": "{name} (stored together with the session)",
        "ru": "{name} (хранится вместе с сессией)",
    },
    # ---------- docgen ----------
    "doc_title": {"az": "TEXNİKİ TAPŞIRIQ (TZ)", "en": "TECHNICAL SPECIFICATION (TZ)", "ru": "ТЕХНИЧЕСКОЕ ЗАДАНИЕ (ТЗ)"},
    "doc_project": {"az": "Layihə", "en": "Project", "ru": "Проект"},
    "doc_date": {"az": "Tarix", "en": "Date", "ru": "Дата"},
    "doc_no_data": {"az": "Məlumat toplanmayıb.", "en": "No information collected.", "ru": "Информация не собрана."},
    "doc_open_head": {
        "az": "Açıq suallar (developer ilə dəqiqləşdirilməlidir)",
        "en": "Open questions (to be clarified with the client)",
        "ru": "Открытые вопросы (уточнить с клиентом)",
    },
    "doc_open_none": {
        "az": "Açıq sual yoxdur — müştəri əsas sahələri cavablayıb.",
        "en": "No open questions — the client answered the main fields.",
        "ru": "Открытых вопросов нет — клиент ответил на основные поля.",
    },
    "doc_annex": {
        "az": "Əlavə 1. Modul saatları (hesablama əsası)",
        "en": "Appendix 1. Module hours (basis of calculation)",
        "ru": "Приложение 1. Часы по модулям (основа расчёта)",
    },
    "doc_th_page": {"az": "Səhifə", "en": "Page", "ru": "Страница"},
    "doc_th_module": {"az": "Modul", "en": "Module", "ru": "Модуль"},
    "doc_th_hours": {"az": "Saat", "en": "Hours", "ru": "Часы"},
    "doc_manual": {"az": "əl ilə qiymətləndirilməlidir", "en": "must be estimated manually", "ru": "требует ручной оценки"},
    "doc_rate": {
        "az": "Saat tarifi: {rate} AZN. Hesablama qaydalarla aparılıb; təxmini xarakter daşıyır.",
        "en": "Hourly rate: {rate} AZN. The calculation is rule-based and approximate.",
        "ru": "Почасовая ставка: {rate} AZN. Расчёт выполнен по правилам и является ориентировочным.",
    },
    "est_tag": {"az": " (təxmin)", "en": " (estimate)", "ru": " (оценка)"},
    "open_tag": {"az": " (açıq sual)", "en": " (open question)", "ru": " (открытый вопрос)"},
}
