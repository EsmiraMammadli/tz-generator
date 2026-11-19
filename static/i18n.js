/* Interfeys tərcüməsi (AZ/EN/RU). Açar = Azərbaycan mətni (HTML-də və app.js-də olduğu kimi).
   Tərcümə tapılmasa AZ mətni göstərilir. Statik HTML DOM gəzintisi ilə, dinamik mətnlər T() ilə tərcümə olunur. */
(function () {
  'use strict';

  const UI = {
    en: {
      'Digər (yazın)...': 'Other (type it)...',
      'Developer ilə dəqiqləşdirəcəm': 'I will clarify with the developer',
      'Səhifənin məzmunu': 'Page content',
      'Dəyişiklik yadda saxlanıldı.': 'Your change was saved.',
      'Bu düzəlişə görə yeni suallar əlavə olundu. Söhbətdə cavablandıra bilərsiniz.': 'This change added new questions. You can answer them in the chat.',
      'Artıq lazım olmayan məlumat silindi: {list}.': 'Information that is no longer needed was removed: {list}.',
      'Qəbul olunmadı: {list}.': 'Not accepted: {list}.',
      'Cavab qəbul olunmadı. Dəyəri yoxlayıb yenidən yazın.': 'The answer was not accepted. Please check the value and try again.',
      'Məzmun: {text}': 'Content: {text}',
      'Fayl əlavə et (loqo, brend bələdçisi, skrinşot)': 'Attach a file (logo, brand guide, screenshot)',
      'Fayl əlavə et': 'Attach a file',
      'Brend bələdçisi (PDF)': 'Brand guide (PDF)',
      'Bir neçə fayl seçə bilərsiniz. PNG / JPG / PDF, hər biri maks. 2 MB': 'You can pick several files. PNG / JPG / PDF, up to 2 MB each',
      'Skrinşot yüklə': 'Upload screenshots',
      'Bir neçə şəkil seçə bilərsiniz. PNG / JPG, hər biri maks. 2 MB': 'You can pick several images. PNG / JPG, up to 2 MB each',
      'Loqo (PNG/JPG)': 'Logo (PNG/JPG)',
      'Dizayn skrinşotu (PNG/JPG)': 'Design screenshot (PNG/JPG)',
      'Bir dəfəyə ən çox {n} fayl yükləyə bilərsiniz.': 'You can upload at most {n} files at once.',
      'Brend bələdçisi yalnız PDF ola bilər.': 'The brand guide must be a PDF.',
      'Yalnız PNG və ya JPG yükləyə bilərsiniz.': 'You can only upload PNG or JPG files.',
      'Fayl qəbul olunmadı: loqo və skrinşot üçün PNG/JPG, bələdçi üçün PDF, hər biri maksimum 2 MB.': 'The file was not accepted: PNG/JPG for logos and screenshots, PDF for the brand guide, 2 MB maximum each.',
      'Fayl sayı limiti aşılıb ({n}). Lazımsız faylı xülasə ekranından silə bilərsiniz.': 'File limit reached ({n}). You can delete an unneeded file on the summary screen.',
      'Loqo': 'Logo',
      'Dizayn nümunəsi': 'Design reference',
      'Yüklənmiş fayllar': 'Uploaded files',
      'Yüklənmiş fayllar (.zip)': 'Uploaded files (.zip)',
      'Loqolar, brend bələdçisi və dizayn skrinşotları bir arxivdə.': 'Logos, brand guide and design screenshots in one archive.',
      'ZIP Yüklə': 'Download ZIP',
      'Niyə soruşuruq: {text}': 'Why we ask: {text}',
      'Məzmun: dəqiqləşdirilməyib': 'Content: not specified yet',
      'Dil seçimi': 'Language',
      'Sessiyanı sıfırla': 'Reset the session',
      'Sıfırla': 'Reset',
      'İnternet bağlantısı kəsilib və ya AI cavab vermir.': 'The internet connection was lost or the AI is not responding.',
      'Yenidən cəhd et': 'Try again',
      'Sadə və Aydın Texniki Tapşırıq': 'Simple and Clear Technical Specification',
      'Saytınız üçün texniki tapşırığı birlikdə hazırlayaq': "Let's prepare the technical specification for your website together",
      'Mürəkkəb terminlər yoxdur. AI köməkçimiz sizə sadə suallar verəcək, ehtiyaclarınızı dinləyəcək və cəmi 10–15 dəqiqəyə proqramçılar üçün hazır TZ sənədi tərtib edəcək.':
        'No complicated terms. Our AI assistant will ask you simple questions, listen to your needs and, in just 10–15 minutes, prepare a TZ document ready for developers.',
      'Suallara cavab verin': 'Answer the questions',
      'Saytın məqsədi, bölmələri, dizayn tələbləri və büdcəsi haqqında qısa söhbət edin.': "Have a short chat about the site's purpose, sections, design requirements and budget.",
      'Xülasəni təsdiqləyin': 'Confirm the summary',
      'Toplanan bütün məlumatları, səhifə ağacını və tələbləri yoxlayıb dəqiqləşdirin.': 'Review and refine all the collected information, the page tree and the requirements.',
      'TZ-ni yükləyin': 'Download the TZ',
      'Hazır texniki tapşırığı rəsmi PDF və DOCX formatında dərhal əldə edin.': 'Get the finished specification right away as an official PDF and DOCX.',
      'Məlumatların emalı razılığı': 'Consent to data processing',
      'Məlumatların qorunması:': 'Data protection:',
      'Daxil etdiyiniz məlumatlar yalnız layihəniz üçün TZ formalaşdırmaq məqsədilə saxlanılır. Zəhmət olmasa həssas məlumatlar (şifrə, kart nömrəsi və s.) qeyd etməyin.':
        'The information you enter is stored only to create the TZ for your project. Please do not enter sensitive data (passwords, card numbers, etc.).',
      'Söhbətə Başla': 'Start the chat',
      'Əvvəlki yarımçıq qalmış sessiyanı bərpa et': 'Restore the previous unfinished session',
      'AI Layihə Məsləhətçisi': 'AI Project Advisor',
      'Veb sayt tələblərinin müəyyənləşdirilməsi': 'Defining website requirements',
      'İrəliləyiş': 'Progress',
      'Xülasəyə Keç': 'Go to summary',
      'AI cavab yazır': 'The AI is typing',
      'AI düşünür': 'The AI is thinking',
      'Loqo yüklə (PNG/JPG, maks. 2 MB)': 'Upload a logo (PNG/JPG, max 2 MB)',
      'Loqo yüklə': 'Upload a logo',
      'Cavabınızı bura yazın... (Enter göndərir, Shift+Enter yeni sətir)': 'Type your answer here... (Enter sends, Shift+Enter adds a new line)',
      'Mesajınızı daxil edin': 'Enter your message',
      'Göndər': 'Send',
      'Dəqiq cavablar daha dolğun TZ yaradır': 'Precise answers create a fuller TZ',
      'TZ İrəliləyişi': 'TZ progress',
      'Ümumi doluluq': 'Overall completion',
      'Xülasəni İncələ': 'Review the summary',
      'Texniki Tapşırıq Xülasəsi': 'Technical Specification Summary',
      'Bütün toplanmış məlumatları nəzərdən keçirin. Dəyişiklik lazımdırsa, söhbətə qayıdıb düzəliş edə bilərsiniz.':
        'Review all the collected information. If you need changes, you can go back to the chat and make corrections.',
      'Aydınlaşdırma tələb edən tələblər': 'Requirements that need clarification',
      'Düzəliş etmək istəyirəm': 'I want to make changes',
      'Təsdiq et və TZ yarat': 'Confirm and create the TZ',
      'Texniki tapşırığınız hazırdır!': 'Your technical specification is ready!',
      'Sənəd uğurla tərtib edildi və standartlara uyğun formatlaşdırıldı.': 'The document was prepared successfully and formatted to standards.',
      'Düzəlişlər etmək və komanda ilə redaktə üçün idealdır.': 'Ideal for making edits and editing with your team.',
      'DOCX Yüklə': 'Download DOCX',
      'Çap etmək, müqaviləyə əlavə etmək və göndərmək üçün.': 'For printing, attaching to a contract and sending.',
      'PDF Yüklə': 'Download PDF',
      'Sənədin İlkin Baxışı (Özət)': 'Document preview (excerpt)',
      'Süni intellekt köməkçimizdən razı qaldınızmı?': 'Were you satisfied with our AI assistant?',
      'Qiymətləndirməniz sistemi təkmilləşdirməyə kömək edir.': 'Your rating helps improve the system.',
      'Təklif və ya fikirləriniz...': 'Your suggestions or thoughts...',
      'Rəyi Göndər': 'Send feedback',
      'Məxfiliyin idarə olunması': 'Privacy control',
      'İşiniz bitdikdən sonra bütün layihə qeydlərini serverlərimizdən silə bilərsiniz.': 'When you are finished, you can delete all project records from our servers.',
      'Bütün məlumatlarımı sil': 'Delete all my data',
      'Məlumatları silmək istəyirsiniz?': 'Do you want to delete the data?',
      'Bu əməliyyat geri qaytarılmaz. Yaradılmış texniki tapşırıq və sessiya qeydləri birdəfəlik silinəcəkdir.':
        'This action cannot be undone. The generated specification and session records will be permanently deleted.',
      'Ləğv et': 'Cancel',
      'Bəli, tamamilə sil': 'Yes, delete everything',
      'Təklif olunan sayt strukturu': 'Suggested site structure',
      'Redaktə edilə bilər': 'Editable',
      'Yeni səhifə əlavə et': 'Add a new page',
      'AI TZ Generatoru — Veb Layihələr üçün Texniki Tapşırıq Hazırlayıcısı': 'AI TZ Generator — Technical Specification Builder for Web Projects',
      // ---- dinamik (app.js) ----
      'İnternet bağlantısı kəsilib. Bağlantını yoxlayıb yenidən cəhd edin.': 'The internet connection was lost. Check it and try again.',
      'AI köməkçi hazırda cavab vermir. Bir az sonra yenidən cəhd edin.': 'The AI assistant is not responding right now. Please try again in a moment.',
      'Çox tez-tez mesaj göndərdiniz. {s} saniyə gözləyib yenidən cəhd edin.': 'You sent messages too quickly. Wait {s} seconds and try again.',
      'Sessiyanın vaxtı keçib və ya silinib. Yeni söhbətə başlaya bilərsiniz.': 'The session has expired or was deleted. You can start a new chat.',
      'Yeni başla': 'Start new',
      'Mesaj çox uzundur və ya boşdur (maksimum 2000 simvol).': 'The message is too long or empty (maximum 2000 characters).',
      'PDF hazırda yaradıla bilmir. DOCX formatını yükləyə bilərsiniz.': 'The PDF cannot be created right now. You can download the DOCX instead.',
      'TZ hələ tam deyil: {list}': 'The TZ is not complete yet: {list}',
      'Söhbətə qayıt': 'Back to the chat',
      'Gözlənilməz xəta baş verdi. Yenidən cəhd edin.': 'An unexpected error occurred. Please try again.',
      'xüsusi': 'custom',
      'Tamamlandı': 'Completed', 'Davam edir': 'In progress', 'Gözləyir': 'Pending',
      'Siz dediniz': 'You said it', 'Təxmin edildi (təsdiq lazımdır)': 'Estimated (needs confirmation)', 'Şablondan': 'From template',
      'Hesablanıb': 'Calculated', 'Dəqiqləşdirilməlidir': 'To be clarified', 'Rəngləri göndər': 'Send colors',
      'Rəng əlavə et': 'Add a color', 'Rəng seç': 'Pick a color',
      '+ {n} standart tələb': '+ {n} standard requirements',
      '⚠️ Diqqət': '⚠️ Attention',
      'əl ilə qiymətləndirilməlidir': 'must be estimated manually',
      'Məlumat hələ toplanmayıb.': 'No information collected yet.',
      'TZ hələ tam deyil': 'The TZ is not complete yet',
      'Çatışmayan: {list}': 'Missing: {list}',
      'Mərhələ': 'Phase', 'Müddət': 'Duration', 'Saat': 'Hours', 'Ümumi': 'Total',
      '{n} iş günü': '{n} working days',
      '{lo}–{hi} həftə': '{lo}–{hi} weeks',
      'TEXNİKİ TAPŞIRIQ (TZ)': 'TECHNICAL SPECIFICATION (TZ)',
      'Layihə: {name} • Tarix: {date}': 'Project: {name} • Date: {date}',
      'Tam məzmun DOCX/PDF faylındadır.': 'The full content is in the DOCX/PDF file.',
      ' Başladılır...': ' Starting...',
      ' Sənəd hazırlanır...': ' Preparing the document...',
      ' Təsdiq et və TZ yarat': ' Confirm and create the TZ',
      'Yalnız PNG və ya JPG loqo yükləyə bilərsiniz.': 'You can only upload a PNG or JPG logo.',
      'Fayl 2 MB-dan böyük olmamalıdır.': 'The file must not be larger than 2 MB.',
      'Fayl qəbul olunmadı: yalnız PNG/JPG, maksimum 2 MB.': 'The file was not accepted: PNG/JPG only, maximum 2 MB.',
      'Loqo qəbul edildi: {name}. Texniki tapşırığa əlavə olunacaq.': 'Logo received: {name}. It will be added to the technical specification.',
      'Bütün məlumatlarınız silindi.': 'All your data has been deleted.',
      'Təşəkkür edirik!': 'Thank you!',
      'Əminsiniz? (yenidən basın)': 'Are you sure? (click again)',
      'İnternet bağlantısı kəsilib.': 'The internet connection was lost.',
      'Dili yalnız söhbətin əvvəlində seçmək olar. Yeni dildə başlamaq üçün «Sıfırla» düyməsini basın.':
        'The language can only be chosen at the start of the chat. Press “Reset” to start again in another language.',
      'Strukturu dəyişmək üçün kartdakı qələm (adı dəyiş), zibil qutusu (sil) və «Yeni səhifə əlavə et» düymələrindən istifadə edin. Başqa cavabı dəyişmək üçün yazın, məsələn: «Dilləri AZ + EN et».':
        'To change the structure, use the pencil (edit), the trash can (delete) and “Add a new page” on the card, or type what you want in the box under it. To change another answer, write it, for example: “Set the languages to AZ + EN”.',
      'Dəyiş': 'Edit', 'Sil': 'Delete', 'Saxla': 'Save', 'Əlavə et': 'Add',
      'Səhifənin adı': 'Page name', 'Qısa təsvir (ixtiyari)': 'Short description (optional)',
      'Nə əlavə etmək və ya dəyişmək istəyirsiniz? Özünüz yazın...': 'What would you like to add or change? Write it yourself...',
    },
    ru: {
      'Digər (yazın)...': 'Другое (напишите)...',
      'Developer ilə dəqiqləşdirəcəm': 'Уточню с разработчиком',
      'Səhifənin məzmunu': 'Содержимое страницы',
      'Dəyişiklik yadda saxlanıldı.': 'Изменение сохранено.',
      'Bu düzəlişə görə yeni suallar əlavə olundu. Söhbətdə cavablandıra bilərsiniz.': 'Из-за этого изменения появились новые вопросы. Вы можете ответить на них в чате.',
      'Artıq lazım olmayan məlumat silindi: {list}.': 'Ненужная информация удалена: {list}.',
      'Qəbul olunmadı: {list}.': 'Не принято: {list}.',
      'Cavab qəbul olunmadı. Dəyəri yoxlayıb yenidən yazın.': 'Ответ не принят. Проверьте значение и попробуйте снова.',
      'Məzmun: {text}': 'Контент: {text}',
      'Fayl əlavə et (loqo, brend bələdçisi, skrinşot)': 'Прикрепить файл (логотип, брендбук, скриншот)',
      'Fayl əlavə et': 'Прикрепить файл',
      'Brend bələdçisi (PDF)': 'Брендбук (PDF)',
      'Bir neçə fayl seçə bilərsiniz. PNG / JPG / PDF, hər biri maks. 2 MB': 'Можно выбрать несколько файлов. PNG / JPG / PDF, до 2 МБ каждый',
      'Skrinşot yüklə': 'Загрузить скриншоты',
      'Bir neçə şəkil seçə bilərsiniz. PNG / JPG, hər biri maks. 2 MB': 'Можно выбрать несколько изображений. PNG / JPG, до 2 МБ каждое',
      'Loqo (PNG/JPG)': 'Логотип (PNG/JPG)',
      'Dizayn skrinşotu (PNG/JPG)': 'Скриншот дизайна (PNG/JPG)',
      'Bir dəfəyə ən çox {n} fayl yükləyə bilərsiniz.': 'За один раз можно загрузить не более {n} файлов.',
      'Brend bələdçisi yalnız PDF ola bilər.': 'Брендбук может быть только в формате PDF.',
      'Yalnız PNG və ya JPG yükləyə bilərsiniz.': 'Можно загружать только PNG или JPG.',
      'Fayl qəbul olunmadı: loqo və skrinşot üçün PNG/JPG, bələdçi üçün PDF, hər biri maksimum 2 MB.': 'Файл не принят: PNG/JPG для логотипов и скриншотов, PDF для брендбука, максимум 2 МБ каждый.',
      'Fayl sayı limiti aşılıb ({n}). Lazımsız faylı xülasə ekranından silə bilərsiniz.': 'Достигнут лимит файлов ({n}). Ненужный файл можно удалить на экране сводки.',
      'Loqo': 'Логотип',
      'Dizayn nümunəsi': 'Пример дизайна',
      'Yüklənmiş fayllar': 'Загруженные файлы',
      'Yüklənmiş fayllar (.zip)': 'Загруженные файлы (.zip)',
      'Loqolar, brend bələdçisi və dizayn skrinşotları bir arxivdə.': 'Логотипы, брендбук и скриншоты дизайна в одном архиве.',
      'ZIP Yüklə': 'Скачать ZIP',
      'Niyə soruşuruq: {text}': 'Зачем мы спрашиваем: {text}',
      'Məzmun: dəqiqləşdirilməyib': 'Контент: пока не уточнён',
      'Dil seçimi': 'Язык',
      'Sessiyanı sıfırla': 'Сбросить сессию',
      'Sıfırla': 'Сброс',
      'İnternet bağlantısı kəsilib və ya AI cavab vermir.': 'Нет подключения к интернету или ИИ не отвечает.',
      'Yenidən cəhd et': 'Повторить',
      'Sadə və Aydın Texniki Tapşırıq': 'Простое и понятное техническое задание',
      'Saytınız üçün texniki tapşırığı birlikdə hazırlayaq': 'Давайте вместе подготовим техническое задание для вашего сайта',
      'Mürəkkəb terminlər yoxdur. AI köməkçimiz sizə sadə suallar verəcək, ehtiyaclarınızı dinləyəcək və cəmi 10–15 dəqiqəyə proqramçılar üçün hazır TZ sənədi tərtib edəcək.':
        'Никаких сложных терминов. Наш ИИ-помощник задаст простые вопросы, выслушает ваши потребности и всего за 10–15 минут подготовит ТЗ, готовое для программистов.',
      'Suallara cavab verin': 'Ответьте на вопросы',
      'Saytın məqsədi, bölmələri, dizayn tələbləri və büdcəsi haqqında qısa söhbət edin.': 'Коротко расскажите о цели сайта, его разделах, требованиях к дизайну и бюджете.',
      'Xülasəni təsdiqləyin': 'Подтвердите сводку',
      'Toplanan bütün məlumatları, səhifə ağacını və tələbləri yoxlayıb dəqiqləşdirin.': 'Проверьте и уточните всю собранную информацию, дерево страниц и требования.',
      'TZ-ni yükləyin': 'Скачайте ТЗ',
      'Hazır texniki tapşırığı rəsmi PDF və DOCX formatında dərhal əldə edin.': 'Получите готовое техническое задание сразу в официальном формате PDF и DOCX.',
      'Məlumatların emalı razılığı': 'Согласие на обработку данных',
      'Məlumatların qorunması:': 'Защита данных:',
      'Daxil etdiyiniz məlumatlar yalnız layihəniz üçün TZ formalaşdırmaq məqsədilə saxlanılır. Zəhmət olmasa həssas məlumatlar (şifrə, kart nömrəsi və s.) qeyd etməyin.':
        'Введённые вами данные хранятся только для составления ТЗ по вашему проекту. Пожалуйста, не указывайте конфиденциальные данные (пароли, номера карт и т. д.).',
      'Söhbətə Başla': 'Начать чат',
      'Əvvəlki yarımçıq qalmış sessiyanı bərpa et': 'Восстановить прерванную сессию',
      'AI Layihə Məsləhətçisi': 'ИИ-консультант по проекту',
      'Veb sayt tələblərinin müəyyənləşdirilməsi': 'Определение требований к веб-сайту',
      'İrəliləyiş': 'Прогресс',
      'Xülasəyə Keç': 'Перейти к сводке',
      'AI cavab yazır': 'ИИ печатает',
      'AI düşünür': 'ИИ думает',
      'Loqo yüklə (PNG/JPG, maks. 2 MB)': 'Загрузить логотип (PNG/JPG, макс. 2 МБ)',
      'Loqo yüklə': 'Загрузить логотип',
      'Cavabınızı bura yazın... (Enter göndərir, Shift+Enter yeni sətir)': 'Введите ответ здесь... (Enter отправляет, Shift+Enter — новая строка)',
      'Mesajınızı daxil edin': 'Введите ваше сообщение',
      'Göndər': 'Отправить',
      'Dəqiq cavablar daha dolğun TZ yaradır': 'Точные ответы дают более полное ТЗ',
      'TZ İrəliləyişi': 'Прогресс ТЗ',
      'Ümumi doluluq': 'Общая заполненность',
      'Xülasəni İncələ': 'Просмотреть сводку',
      'Texniki Tapşırıq Xülasəsi': 'Сводка технического задания',
      'Bütün toplanmış məlumatları nəzərdən keçirin. Dəyişiklik lazımdırsa, söhbətə qayıdıb düzəliş edə bilərsiniz.':
        'Просмотрите всю собранную информацию. Если нужны изменения, вернитесь в чат и внесите правки.',
      'Aydınlaşdırma tələb edən tələblər': 'Требования, нуждающиеся в уточнении',
      'Düzəliş etmək istəyirəm': 'Хочу внести изменения',
      'Təsdiq et və TZ yarat': 'Подтвердить и создать ТЗ',
      'Texniki tapşırığınız hazırdır!': 'Ваше техническое задание готово!',
      'Sənəd uğurla tərtib edildi və standartlara uyğun formatlaşdırıldı.': 'Документ успешно составлен и оформлен по стандартам.',
      'Düzəlişlər etmək və komanda ilə redaktə üçün idealdır.': 'Идеально для правок и совместного редактирования.',
      'DOCX Yüklə': 'Скачать DOCX',
      'Çap etmək, müqaviləyə əlavə etmək və göndərmək üçün.': 'Для печати, приложения к договору и отправки.',
      'PDF Yüklə': 'Скачать PDF',
      'Sənədin İlkin Baxışı (Özət)': 'Предпросмотр документа (выдержка)',
      'Süni intellekt köməkçimizdən razı qaldınızmı?': 'Довольны ли вы нашим ИИ-помощником?',
      'Qiymətləndirməniz sistemi təkmilləşdirməyə kömək edir.': 'Ваша оценка помогает улучшать систему.',
      'Təklif və ya fikirləriniz...': 'Ваши предложения или мнение...',
      'Rəyi Göndər': 'Отправить отзыв',
      'Məxfiliyin idarə olunması': 'Управление конфиденциальностью',
      'İşiniz bitdikdən sonra bütün layihə qeydlərini serverlərimizdən silə bilərsiniz.': 'Когда вы закончите, вы можете удалить все записи проекта с наших серверов.',
      'Bütün məlumatlarımı sil': 'Удалить все мои данные',
      'Məlumatları silmək istəyirsiniz?': 'Хотите удалить данные?',
      'Bu əməliyyat geri qaytarılmaz. Yaradılmış texniki tapşırıq və sessiya qeydləri birdəfəlik silinəcəkdir.':
        'Это действие необратимо. Созданное ТЗ и записи сессии будут удалены навсегда.',
      'Ləğv et': 'Отмена',
      'Bəli, tamamilə sil': 'Да, удалить всё',
      'Təklif olunan sayt strukturu': 'Предлагаемая структура сайта',
      'Redaktə edilə bilər': 'Можно редактировать',
      'Yeni səhifə əlavə et': 'Добавить новую страницу',
      'AI TZ Generatoru — Veb Layihələr üçün Texniki Tapşırıq Hazırlayıcısı': 'AI TZ Generator — конструктор технических заданий для веб-проектов',
      // ---- dinamik (app.js) ----
      'İnternet bağlantısı kəsilib. Bağlantını yoxlayıb yenidən cəhd edin.': 'Соединение с интернетом потеряно. Проверьте его и повторите попытку.',
      'AI köməkçi hazırda cavab vermir. Bir az sonra yenidən cəhd edin.': 'ИИ-помощник сейчас не отвечает. Попробуйте ещё раз чуть позже.',
      'Çox tez-tez mesaj göndərdiniz. {s} saniyə gözləyib yenidən cəhd edin.': 'Вы отправляете сообщения слишком часто. Подождите {s} с и повторите.',
      'Sessiyanın vaxtı keçib və ya silinib. Yeni söhbətə başlaya bilərsiniz.': 'Сессия истекла или была удалена. Вы можете начать новый чат.',
      'Yeni başla': 'Начать заново',
      'Mesaj çox uzundur və ya boşdur (maksimum 2000 simvol).': 'Сообщение слишком длинное или пустое (максимум 2000 символов).',
      'PDF hazırda yaradıla bilmir. DOCX formatını yükləyə bilərsiniz.': 'PDF сейчас создать нельзя. Вы можете скачать DOCX.',
      'TZ hələ tam deyil: {list}': 'ТЗ ещё не полное: {list}',
      'Söhbətə qayıt': 'Вернуться в чат',
      'Gözlənilməz xəta baş verdi. Yenidən cəhd edin.': 'Произошла непредвиденная ошибка. Повторите попытку.',
      'xüsusi': 'особое',
      'Tamamlandı': 'Готово', 'Davam edir': 'В процессе', 'Gözləyir': 'Ожидает',
      'Siz dediniz': 'Вы сказали', 'Təxmin edildi (təsdiq lazımdır)': 'Предположено (нужно подтверждение)', 'Şablondan': 'Из шаблона',
      'Hesablanıb': 'Рассчитано', 'Dəqiqləşdirilməlidir': 'Нужно уточнить', 'Rəngləri göndər': 'Отправить цвета',
      'Rəng əlavə et': 'Добавить цвет', 'Rəng seç': 'Выбрать цвет',
      '+ {n} standart tələb': '+ {n} стандартных требований',
      '⚠️ Diqqət': '⚠️ Внимание',
      'əl ilə qiymətləndirilməlidir': 'требует ручной оценки',
      'Məlumat hələ toplanmayıb.': 'Информация ещё не собрана.',
      'TZ hələ tam deyil': 'ТЗ ещё не полное',
      'Çatışmayan: {list}': 'Не хватает: {list}',
      'Mərhələ': 'Этап', 'Müddət': 'Срок', 'Saat': 'Часы', 'Ümumi': 'Итого',
      '{n} iş günü': '{n} рабочих дн.',
      '{lo}–{hi} həftə': '{lo}–{hi} нед.',
      'TEXNİKİ TAPŞIRIQ (TZ)': 'ТЕХНИЧЕСКОЕ ЗАДАНИЕ (ТЗ)',
      'Layihə: {name} • Tarix: {date}': 'Проект: {name} • Дата: {date}',
      'Tam məzmun DOCX/PDF faylındadır.': 'Полное содержание находится в файле DOCX/PDF.',
      ' Başladılır...': ' Запуск...',
      ' Sənəd hazırlanır...': ' Документ готовится...',
      ' Təsdiq et və TZ yarat': ' Подтвердить и создать ТЗ',
      'Yalnız PNG və ya JPG loqo yükləyə bilərsiniz.': 'Можно загрузить только логотип в PNG или JPG.',
      'Fayl 2 MB-dan böyük olmamalıdır.': 'Файл не должен быть больше 2 МБ.',
      'Fayl qəbul olunmadı: yalnız PNG/JPG, maksimum 2 MB.': 'Файл не принят: только PNG/JPG, максимум 2 МБ.',
      'Loqo qəbul edildi: {name}. Texniki tapşırığa əlavə olunacaq.': 'Логотип получен: {name}. Он будет добавлен в техническое задание.',
      'Bütün məlumatlarınız silindi.': 'Все ваши данные удалены.',
      'Təşəkkür edirik!': 'Спасибо!',
      'Əminsiniz? (yenidən basın)': 'Вы уверены? (нажмите ещё раз)',
      'İnternet bağlantısı kəsilib.': 'Соединение с интернетом потеряно.',
      'Dili yalnız söhbətin əvvəlində seçmək olar. Yeni dildə başlamaq üçün «Sıfırla» düyməsini basın.':
        'Язык можно выбрать только в начале чата. Нажмите «Сброс», чтобы начать заново на другом языке.',
      'Strukturu dəyişmək üçün kartdakı qələm (adı dəyiş), zibil qutusu (sil) və «Yeni səhifə əlavə et» düymələrindən istifadə edin. Başqa cavabı dəyişmək üçün yazın, məsələn: «Dilləri AZ + EN et».':
        'Чтобы изменить структуру, используйте карандаш (изменить), корзину (удалить) и «Добавить новую страницу» на карточке или напишите, что нужно, в поле под ней. Чтобы изменить другой ответ, напишите, например: «Сделай языки AZ + EN».',
      'Dəyiş': 'Изменить', 'Sil': 'Удалить', 'Saxla': 'Сохранить', 'Əlavə et': 'Добавить',
      'Səhifənin adı': 'Название страницы', 'Qısa təsvir (ixtiyari)': 'Краткое описание (необязательно)',
      'Nə əlavə etmək və ya dəyişmək istəyirsiniz? Özünüz yazın...': 'Что вы хотите добавить или изменить? Напишите сами...',
    },
  };

  const KEY = 'ai_tz_ui_lang';
  const norm = (s) => s.replace(/\s+/g, ' ').trim();
  let lang = 'az';

  function T(az, vars) {
    let r = az;
    if (lang !== 'az') {
      const d = UI[lang] || {};
      r = d[az] || d[norm(az)] || az;
      // başında/sonunda boşluq olan açarlar (məs. ' Başladılır...') üçün
      if (r === az && d[az.trim()]) r = (az.startsWith(' ') ? ' ' : '') + d[az.trim()] + (az.endsWith(' ') ? ' ' : '');
    }
    if (vars) for (const k of Object.keys(vars)) r = r.split('{' + k + '}').join(String(vars[k]));
    return r;
  }

  function translateTextNode(n) {
    if (n.__az === undefined) n.__az = n.nodeValue;
    const key = norm(n.__az);
    if (!key) return;
    const tr = lang === 'az' ? null : (UI[lang] || {})[key];
    if (tr) {
      const lead = /^\s/.test(n.__az) ? ' ' : '';
      const trail = /\s$/.test(n.__az) ? ' ' : '';
      n.nodeValue = lead + tr + trail;
    } else {
      n.nodeValue = n.__az;
    }
  }

  function walk(root) {
    const w = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
      acceptNode: (n) => (n.parentNode && /^(SCRIPT|STYLE)$/.test(n.parentNode.nodeName) ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT),
    });
    const nodes = [];
    while (w.nextNode()) nodes.push(w.currentNode);
    nodes.forEach(translateTextNode);
    const scope = root.querySelectorAll ? root.querySelectorAll('[placeholder],[title],[aria-label]') : [];
    scope.forEach((el) => {
      ['placeholder', 'title', 'aria-label'].forEach((a) => {
        if (!el.hasAttribute(a)) return;
        const store = 'az' + a.replace('-', '');
        if (el.dataset[store] === undefined) el.dataset[store] = el.getAttribute(a);
        const orig = el.dataset[store];
        const tr = lang === 'az' ? null : (UI[lang] || {})[norm(orig)];
        el.setAttribute(a, tr || orig);
      });
    });
  }

  function applyAll() {
    document.documentElement.lang = lang;
    walk(document.body);
    document.querySelectorAll('template').forEach((t) => walk(t.content));
    const titleKey = 'AI TZ Generatoru — Veb Layihələr üçün Texniki Tapşırıq Hazırlayıcısı';
    document.title = lang === 'az' ? titleKey : (UI[lang][titleKey] || titleKey);
    document.querySelectorAll('.lang-btn').forEach((b) => b.classList.toggle('active', b.dataset.lang === lang));
  }

  function setLang(l, persist = true) {
    lang = ['az', 'en', 'ru'].includes(l) ? l : 'az';
    if (persist) { try { localStorage.setItem(KEY, lang); } catch (e) { /* private rejim */ } }
    applyAll();
  }

  function savedLang() {
    try { const v = localStorage.getItem(KEY); return ['az', 'en', 'ru'].includes(v) ? v : 'az'; } catch (e) { return 'az'; }
  }

  window.I18N = { T, setLang, savedLang, getLang: () => lang, apply: applyAll };
  window.T = T;
})();
