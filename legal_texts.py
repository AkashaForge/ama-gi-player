"""Юридические тексты Amagi-Player.

v2.0 (2026-10-28):
  - PRIVACY_SECTIONS приведены в соответствие с фактической структурой
    файлов: data/app_data.db, data/cache/, .env, data/mode.txt,
    data/whitelist.db, data/sources.txt;
  - удалены фиктивные config.json и cache/metadata.db;
  - добавлен эндпоинт API Кинопоиска (B.2);
  - добавлено явное раскрытие API-ключа (п. 6.2);
  - расширена матрица соответствия: EU (GDPR) + US (COPPA, CCPA/CPRA,
    VCDPA, CPA, CTDPA) + RU (152-ФЗ);
  - дисклеймер оставлен без изменений (не касается файлов данных).

Структура:
  DISCLAIMER_TITLE / DISCLAIMER_SECTIONS     — Terms of Use (EN)
  DISCLAIMER_TITLE_RU / DISCLAIMER_SECTIONS_RU — Terms of Use (RU)
  PRIVACY_TITLE / PRIVACY_SECTIONS           — Privacy Policy (EN)
  PRIVACY_TITLE_RU / PRIVACY_SECTIONS_RU     — Privacy Policy (RU)

Использование:
  from legal_texts import get_disclaimer, get_privacy
  d = get_disclaimer("en")   # {"title": ..., "version": ..., "sections": [...]}
  p = get_privacy("ru")
"""

# Amagi-Player — desktop media player for public-domain content
# Copyright (C) 2026 AkashaForge
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

# ============================================================================
#  1. DISCLAIMER — Terms of Use and Disclaimer (English)
# ============================================================================

DISCLAIMER_TITLE = "Terms of Use and Disclaimer"
DISCLAIMER_VERSION = "1.0"
DISCLAIMER_DATE = "2026-01-01"

DISCLAIMER_SECTIONS = [
    {
        "id": "doc",
        "title": "0. About this document",
        "content": """0.1. This document is the Terms of Use and the Disclaimer of the Amagi-Player software ("the Application") and is published in the project repository.

0.2. It follows the layered-notice model: summary, overview, full text, annexes. All layers form a single document and do not contradict each other.

0.3. It forms an integral whole with the Privacy Policy. In case of conflict regarding data processing, the Privacy Policy applies; in all other respects, these Terms apply.

0.4. These Terms do not restrict the rights granted by the GNU GPL v3.0 and do not impose additional restrictions on the Application's source code beyond those in that license.

0.5. These Terms are drafted with due regard to the general principles of copyright, related-rights, and consumer-protection law in the User's jurisdiction and do not limit any mandatory rights the User may have under such law.""",
    },
    {
        "id": "defs",
        "title": "1. Definitions",
        "content": """1.1. "Application" — the Amagi-Player software distributed under the GNU GPL v3.0 license, including source code, executables, configuration files, and documentation.

1.2. "Developer" — the person developing and publishing the Application (AkashaForge).

1.3. "User" — a natural or legal person using the Application in any way, including launching, installing, copying, studying the source code, or any other use.

1.4. "Device" — the User's hardware on which the Application is installed and operates.

1.5. "Content" — audiovisual works, texts, images, and other materials accessible through the Application.

1.6. "Source" — an external network service or local program that the Application contacts to obtain Content or metadata.

1.7. "Default source" — a Source built into the Application and used without additional configuration by the User (Internet Archive and similar open archives).

1.8. "User source" — a Source added by the User via the configuration file data/sources.txt.

1.9. "External program" — third-party software not part of the Application, installed and run by the User independently, and capable of interacting with the Application (e.g., external indexers).

1.10. "Public domain" — a legal status in which a work is not protected by copyright or protection has expired, within the meaning established by the law of the relevant jurisdiction.

1.11. "Applicable law" — the law of the jurisdiction in which the User uses the Application, as well as other norms binding on the User.

1.12. "Rights holder" — a person holding an exclusive right in a work or another legally protected right in relation to the Content.""",
    },
    {
        "id": "summary",
        "title": "2. Summary",
        "content": """2.1. The Application is a technical tool for searching, cataloguing, and playing Content that is in the public domain or distributed by rights holders on open terms.

2.2. The Application does not host, redistribute, or transmit the works themselves to third parties.

2.3. The default sources are open archives (Internet Archive and similar).

2.4. User sources and External programs are connected by the User independently and at the User's own risk.

2.5. The Application is provided "as is", without warranties.

2.6. The Developer is not liable for the actions of the User or of third parties.

2.7. Use of the Application constitutes full acceptance of these Terms.""",
    },
    {
        "id": "overview",
        "title": "3. Overview",
        "content": """3.1. Purpose of the Application:
     - search and playback of public-domain Content;
     - working with open archives;
     - optional use of user-defined sources;
     - optional integration with external indexers.

3.2. What the Application is not:
     - a Content hosting service;
     - a file-sharing service;
     - a BitTorrent tracker;
     - a service providing access to works;
     - an intermediary between the User and the Sources.

3.3. Allocation of responsibility:

     +----------------------+-----------------------------+
     | Party                | Responsibility              |
     +----------------------+-----------------------------+
     | Developer            | operability of the code     |
     |                      | within GPLv3                |
     +----------------------+-----------------------------+
     | User                 | choice of Sources,          |
     |                      | compliance with the laws    |
     |                      | of their jurisdiction       |
     +----------------------+-----------------------------+
     | Owner of the Source  | legal status of the         |
     |                      | published Content           |
     +----------------------+-----------------------------+
     | Developer of an      | operability and security    |
     | External program     | of the External program     |
     +----------------------+-----------------------------+

3.4. Key limitations:
     - the Application does not guarantee the legal status of Content;
     - the Application does not review user sources;
     - the Application does not control External programs;
     - the Application does not provide legal advice.""",
    },
    {
        "id": "art1",
        "title": "Article 1. Acceptance of terms",
        "content": """1.1. By using the Application in any way, including launching, installing, copying, studying the source code, or any other use, the User confirms that they have read these Terms in full, understand their content, and accept them in full without reservation.

1.2. If the User disagrees with any provision of these Terms, the User must stop using the Application and delete all its copies.

1.3. Acceptance of the Terms is recorded in the dialog shown on first launch (LegalGateDialog) and is a mandatory condition for further use.

1.4. Acceptance of the Terms does not waive the User's rights under the GNU GPL v3.0 license.

1.5. Acceptance of the Terms does not waive any mandatory rights of the User under consumer-protection law in their jurisdiction.""",
    },
    {
        "id": "art2",
        "title": "Article 2. Purpose of the application",
        "content": """2.1. The Application is a technical tool for searching, cataloguing, and playing audiovisual Content that is in the public domain or distributed by rights holders on open terms.

2.2. The Application is initially oriented toward open archives (Internet Archive and similar) that publish Content under terms permitting its free playback and distribution.

2.3. The Application is not a means of accessing Content whose distribution violates applicable law.

2.4. The Application's purpose is limited to the functions listed in the project's documentation. Use of the Application outside these functions is not supported by the Developer and is at the User's own risk.

2.5. The Application is not intended to circumvent technological protection measures or other access-control measures.""",
    },
    {
        "id": "art3",
        "title": "Article 3. Nature of the application",
        "content": """3.1. The Application does not contain, store, permanently cache, redistribute, or transmit to third parties the audiovisual works themselves or their fragments.

3.2. The Application is not a hosting service, file-sharing service, BitTorrent tracker, or any other service providing access to works. The Application is client-side software installed on the User's Device.

3.3. All interaction with Content Sources takes place directly from the User's Device. The Developer does not act as an intermediary, agent, or operator of such interactions.

3.4. The Application does not perform any prior review, moderation, or filtering of Content received from Sources.

3.5. The Application's technical mechanisms (including streaming via BitTorrent swarms of open archives) are used solely for the purpose of efficient delivery of Content published by the Sources themselves.

3.6. The Application is not a means of circumventing blocking measures imposed by authorised bodies.""",
    },
    {
        "id": "art4",
        "title": "Article 4. Default sources",
        "content": """4.1. By default, the Application is configured to work with public archives (Internet Archive and similar), whose built-in list is limited to Content that is in the public domain or distributed on lawful grounds.

4.2. Internet Archive and similar archives determine the legal status of the materials they publish on their own.

4.3. The Developer does not guarantee that every item of Content available through a Default source is in the public domain in the User's jurisdiction. The legal status of a work may differ depending on jurisdiction.

4.4. Assessment of the legal status of a particular work remains with the User. The Developer does not provide legal advice and does not perform legal review of Content.

4.5. The Application does not automatically verify licenses or the legal status of Content received from Default sources.""",
    },
    {
        "id": "art5",
        "title": "Article 5. User sources",
        "content": """5.1. The Application allows the User to add their own Sources via the configuration file data/sources.txt, at their own discretion.

5.2. The User fills in configuration files independently and bears full responsibility for:
     - the content of the added Sources;
     - the lawfulness of their use in the User's jurisdiction;
     - any consequences of such use.

5.3. The Developer does not review, control, or endorse the content of User sources, has no access to them, and cannot be held responsible for them.

5.4. User sources are not part of the Application and are not shipped with it.

5.5. The User undertakes not to add to configuration files links to Sources through which Content is distributed in violation of applicable law.

5.6. The Developer may at any time discontinue support for the User sources feature without prior notice.""",
    },
    {
        "id": "art6",
        "title": "Article 6. External programs",
        "content": """6.1. The Application is compatible with certain External programs that the User installs independently. A typical example is an external content indexer such as Jackett.

6.2. External programs:
     - are not part of the Application;
     - are not shipped with the Application;
     - are not developed or supported by the Developer;
     - are distributed under their own licenses;
     - are used by the User at their own risk.

6.3. The Developer is not responsible for the Content to which External programs provide access, for their operation, for vulnerabilities in them, or for any consequences of their use.

6.4. The User undertakes to independently read the licenses and terms of use of External programs before installing and running them.

6.5. The mention of an External program in the Application's documentation is not a recommendation, endorsement, or warranty of its operability, security, or lawfulness.""",
    },
    {
        "id": "art7",
        "title": "Article 7. User obligations",
        "content": """7.1. The User undertakes to use the Application solely for lawful purposes and in compliance with the laws of their jurisdiction.

7.2. The User undertakes not to use the Application for:
     - distribution, public display, or other use of works without the rights holder's consent;
     - circumventing technological protection measures where such circumvention is prohibited by applicable law;
     - distributing malicious software;
     - infringing the rights of third parties;
     - any other activity prohibited by law.

7.3. The User undertakes not to add to configuration files links to Sources through which Content is distributed in violation of applicable law.

7.4. Responsibility for compliance with the laws of the User's jurisdiction rests solely with the User.

7.5. The User is solely responsible for the safety of their Device, their credentials, and any other resources used together with the Application.""",
    },
    {
        "id": "art8",
        "title": "Article 8. Intellectual property",
        "content": """8.1. The Application is distributed under the GNU General Public License v3.0. Licensing terms are set out in the LICENSE file shipped with the Application.

8.2. These Terms do not restrict the rights granted to the User by that license and do not impose additional restrictions on the use of the Application's code beyond those set out in the license.

8.3. Rights in Content obtained through the Application belong to the respective rights holders or are in the public domain in accordance with applicable law.

8.4. The Developer claims no rights in Content obtained through the Application.

8.5. The name "Amagi-Player", the logo, and other means of individualisation of the project may not be used in ways that mislead as to the origin of the Application or its connection with the Developer.""",
    },
    {
        "id": "art9",
        "title": "Article 9. Disclaimer of warranties",
        "content": """9.1. The Application is provided on an "as is" and "as available" basis, without warranties of any kind, express or implied, including, but not limited to, warranties of merchantability, fitness for a particular purpose, and non-infringement of third-party rights.

9.2. The Developer does not warrant:
     - uninterrupted or error-free operation of the Application;
     - the Application's fitness for the User's particular purposes;
     - compatibility with the User's hardware, software, or Sources;
     - preservation of data, watch history, or settings;
     - availability or legal status of Content obtained through Sources;
     - operability of External programs and User sources;
     - the absence of errors, vulnerabilities, or malicious code in the Application's dependencies.

9.3. The Developer may modify, suspend, or discontinue support for the Application at any time without prior notice.

9.4. The User independently assesses the risks of using the Application and accepts all related risks.

9.5. The provisions of this Article apply to the maximum extent permitted by applicable law and do not limit any mandatory rights of the User under consumer-protection law.""",
    },
    {
        "id": "art10",
        "title": "Article 10. Limitation of liability",
        "content": """10.1. To the maximum extent permitted by applicable law, the Developer is not liable for:
      - any direct, indirect, incidental, special, punitive, or consequential damages;
      - loss of data, profits, reputation, or business information;
      - damage arising from the use or inability to use the Application;
      - the User's actions related to the use of the Application;
      - the actions of third parties, including rights holders, Source operators, and developers of External programs;
      - Content obtained through Sources;
      - the consequences of using User sources and External programs.

10.2. The User uses the Application at their own risk and independently assesses the legal consequences of such use in their jurisdiction.

10.3. This limitation of liability applies to the maximum extent permitted by applicable law. If any limitation is held invalid, this does not invalidate the remaining limitations.

10.4. The Developer does not provide legal advice and does not perform legal review of Content, Sources, or External programs.

10.5. This Article does not limit the Developer's liability in cases where such liability cannot be limited by mandatory norms of applicable law.""",
    },
    {
        "id": "art11",
        "title": "Article 11. Data processing",
        "content": """11.1. Processing of the User's data is governed by the Privacy Policy published in the project repository and shown on first launch of the Application.

11.2. The Privacy Policy forms an integral part of these Terms.

11.3. In case of conflict between these Terms and the Privacy Policy regarding data processing, the Privacy Policy applies.

11.4. Data processing is carried out in accordance with applicable data-protection law and other applicable norms.""",
    },
    {
        "id": "art12",
        "title": "Article 12. Changes to the terms",
        "content": """12.1. The Developer may amend these Terms.

12.2. The current version is published in the project repository.

12.3. Changes affecting the User's rights or obligations are recorded in the Changelog at the end of the document.

12.4. Continued use of the Application after changes are published constitutes acceptance of the new version of the Terms.

12.5. For material changes, the Developer may require renewed acceptance of the Terms on the next launch of the Application.""",
    },
    {
        "id": "art13",
        "title": "Article 13. Governing law and dispute resolution",
        "content": """13.1. These Terms are governed in accordance with the principles generally accepted for open-source projects, without reference to any particular national legal system.

13.2. In the event of a dispute, the parties undertake first to attempt to resolve it through negotiation.

13.3. If the dispute is not resolved through negotiation, it shall be resolved in the manner prescribed by applicable law.

13.4. These Terms do not limit any of the User's rights under mandatory norms of the law of their jurisdiction, including consumer rights.""",
    },
    {
        "id": "art14",
        "title": "Article 14. Final provisions",
        "content": """14.1. If any provision of these Terms is held invalid or unenforceable, this does not invalidate the remaining provisions.

14.2. These Terms take effect on the User's first launch of the Application.

14.3. These Terms remain in force indefinitely until replaced by a new version.

14.4. These Terms are drafted in English. Translations into other languages, if any, are for information only; in case of discrepancies, the English version prevails.""",
    },
    {
        "id": "art15",
        "title": "Article 15. Contacts",
        "content": """15.1. Questions concerning these Terms are submitted via the repository's Issues system:
https://github.com/AkashaForge/ama-gi-player/issues

15.2. The Developer does not provide legal advice and does not address individual legal questions from Users.""",
    },
    {
        "id": "art16",
        "title": "Article 16. Relationship with GPLv3",
        "content": """16.1. The Application is distributed under the GNU General Public License v3.0.

16.2. In case of conflict between these Terms and the GPLv3 license regarding rights to use, modify, and distribute the source code, the GPLv3 license applies.

16.3. These Terms are not an additional restriction on the use of the Application's code beyond what is set out in GPLv3.""",
    },
    {
        "id": "annexA",
        "title": "Annex A. Allocation of responsibility",
        "content": """A.1. Responsibility matrix by party and subject:

     +------------------+------------------------------+
     | Subject          | Responsible party            |
     +------------------+------------------------------+
     | Operability of   | Developer (within GPLv3,     |
     | the Application  | "as is")                     |
     | code             |                              |
     +------------------+------------------------------+
     | Legal status of  | Owner of the Source          |
     | Content in the   |                              |
     | Source           |                              |
     +------------------+------------------------------+
     | Choice of        | User                         |
     | Sources          |                              |
     +------------------+------------------------------+
     | Compliance with  | User                         |
     | jurisdiction's   |                              |
     | law              |                              |
     +------------------+------------------------------+
     | Installing and   | User                         |
     | using External   |                              |
     | programs         |                              |
     +------------------+------------------------------+
     | Security of an   | Developer of the External    |
     | External program | program                      |
     +------------------+------------------------------+
     | Preservation of  | User (OS, disk encryption,   |
     | data on the      | backups)                     |
     | Device           |                              |
     +------------------+------------------------------+
     | Network requests | Owner of the Source          |
     | to Sources       |                              |
     +------------------+------------------------------+

A.2. The Developer does not exercise control over:
     - the content of Sources;
     - the availability of Sources;
     - the privacy policies of Sources;
     - the operation of External programs;
     - the configuration of the User's Device.""",
    },
    {
        "id": "annexB",
        "title": "Annex B. Glossary of legal regimes",
        "content": """B.1. Public domain: a legal status in which a work is not protected by copyright or protection has expired. The exact terms and conditions of entry into the public domain are determined by the law of the relevant jurisdiction.

B.2. Open licenses: a family of public licenses that allow a rights holder to pre-determine the terms of use of a work (attribution, non-commercial use, prohibition of derivatives, etc.).

B.3. Open access: a regime of free access to scholarly and educational materials in which the rights holder permits free reading, downloading, and distribution of the work.

B.4. Other open regimes: other licenses and regimes that permit free playback and distribution of a work on terms set by the rights holder.

B.5. The User independently determines whether a particular work falls under one of the listed regimes in their jurisdiction.""",
    },
    {
        "id": "annexC",
        "title": "Annex C. Relationship with applicable law",
        "content": """C.1. These Terms are drafted with due regard to the general principles characteristic of copyright and related-rights law, consumer-protection law, and data-protection law in force in various jurisdictions.

C.2. The Developer does not carry out any activity that contravenes mandatory norms of applicable law.

C.3. With respect to rights to use, modify, and distribute the Application's source code, the GNU GPL v3.0 license applies.

C.4. With respect to data processing, the Privacy Policy published in the project repository applies.

C.5. In case of conflict between these Terms and mandatory norms of applicable law, the relevant mandatory norms apply.

C.6. The User independently determines whether their use of the Application complies with the requirements of their jurisdiction.""",
    },
    {
        "id": "changelog",
        "title": "Changelog",
        "content": """Version 1.0 | 2026-01-01 | Initial publication.
                           Layered structure, Articles 1–16,
                           Annexes A–C.

Amagi-Player · Terms of Use v1.0 · 2026-01-01""",
    },
]


# ============================================================================
#  2. DISCLAIMER — Условия использования (Русский)
# ============================================================================

DISCLAIMER_TITLE_RU = "Условия использования и Отказ от ответственности"
DISCLAIMER_VERSION_RU = "1.0"
DISCLAIMER_DATE_RU = "2026-01-01"

DISCLAIMER_SECTIONS_RU = [
    {
        "id": "doc",
        "title": "0. О настоящем документе",
        "content": """0.1. Настоящий документ является Условиями использования и Отказом от ответственности программного обеспечения Amagi-Player («Приложение») и публикуется в репозитории проекта.

0.2. Документ следует модели многоуровневого уведомления: резюме, обзор, полный текст, приложения. Все уровни образуют единый документ и не противоречат друг другу.

0.3. Документ образует единое целое с Политикой конфиденциальности. В случае противоречия в части обработки данных применяется Политика конфиденциальности; в остальном — настоящие Условия.

0.4. Настоящие Условия не ограничивают права, предоставленные Пользователю лицензией GNU GPL v3.0, и не налагают дополнительных ограничений на использование исходного кода Приложения.

0.5. Настоящие Условия составлены с должным учётом общих принципов законодательства об авторском праве и смежных правах и законодательства о защите прав потребителей, действующих в юрисдикции Пользователя, и не ограничивают императивные права Пользователя по такому законодательству.""",
    },
    {
        "id": "defs",
        "title": "1. Определения",
        "content": """1.1. «Приложение» — программное обеспечение Amagi-Player, распространяемое под лицензией GNU GPL v3.0, включая исходный код, исполняемые файлы, конфигурационные файлы и документацию.

1.2. «Разработчик» — лицо, разрабатывающее и публикующее Приложение (AkashaForge).

1.3. «Пользователь» — физическое или юридическое лицо, использующее Приложение любым способом, включая запуск, установку, копирование, изучение исходного кода или любое иное использование.

1.4. «Устройство» — аппаратное обеспечение Пользователя, на котором установлено и работает Приложение.

1.5. «Контент» — аудиовизуальные произведения, тексты, изображения и иные материалы, доступные через Приложение.

1.6. «Источник» — внешний сетевой сервис или локальная программа, к которой Приложение обращается для получения Контента или метаданных.

1.7. «Источник по умолчанию» — Источник, встроенный в Приложение и используемый без дополнительной настройки (Internet Archive и аналогичные открытые архивы).

1.8. «Пользовательский источник» — Источник, добавленный Пользователем через конфигурационный файл data/sources.txt.

1.9. «Внешняя программа» — стороннее программное обеспечение, не входящее в состав Приложения, устанавливаемое и запускаемое Пользователем самостоятельно и способное взаимодействовать с Приложением.

1.10. «Общественное достояние» — правовой статус, при котором произведение не охраняется авторским правом либо срок охраны истёк, в смысле, установленном законодательством соответствующей юрисдикции.

1.11. «Применимое право» — законодательство юрисдикции, в которой Пользователь использует Приложение, а также иные обязательные для Пользователя нормы.

1.12. «Правообладатель» — лицо, обладающее исключительным правом на произведение или иным охраняемым законом правом в отношении Контента.""",
    },
    {
        "id": "summary",
        "title": "2. Резюме",
        "content": """2.1. Приложение — это технический инструмент для поиска, каталогизации и воспроизведения Контента, находящегося в общественном достоянии или распространяемого правообладателями на открытых условиях.

2.2. Приложение не размещает, не распространяет и не передаёт сами произведения третьим лицам.

2.3. Источники по умолчанию — открытые архивы (Internet Archive и аналогичные).

2.4. Пользовательские источники и Внешние программы подключаются Пользователем самостоятельно и на его собственный риск.

2.5. Приложение предоставляется «как есть», без гарантий.

2.6. Разработчик не несёт ответственности за действия Пользователя или третьих лиц.

2.7. Использование Приложения означает полное принятие настоящих Условий.""",
    },
    {
        "id": "overview",
        "title": "3. Обзор",
        "content": """3.1. Назначение Приложения:
     - поиск и воспроизведение Контента общественного достояния;
     - работа с открытыми архивами;
     - опциональное использование пользовательских источников;
     - опциональная интеграция с внешними индексаторами.

3.2. Чем Приложение не является:
     - хостингом Контента;
     - файлообменным сервисом;
     - BitTorrent-трекером;
     - сервисом, предоставляющим доступ к произведениям;
     - посредником между Пользователем и Источниками.

3.3. Распределение ответственности:

     +----------------------+-----------------------------+
     | Сторона              | Ответственность             |
     +----------------------+-----------------------------+
     | Разработчик          | работоспособность кода      |
     |                      | в рамках GPLv3              |
     +----------------------+-----------------------------+
     | Пользователь         | выбор Источников,           |
     |                      | соблюдение законов своей    |
     |                      | юрисдикции                  |
     +----------------------+-----------------------------+
     | Владелец Источника   | правовой статус             |
     |                      | публикуемого Контента       |
     +----------------------+-----------------------------+
     | Разработчик Внешней  | работоспособность и         |
     | программы            | безопасность Внешней        |
     |                      | программы                   |
     +----------------------+-----------------------------+

3.4. Ключевые ограничения:
     - Приложение не гарантирует правовой статус Контента;
     - Приложение не проверяет пользовательские источники;
     - Приложение не контролирует Внешние программы;
     - Приложение не предоставляет юридических консультаций.""",
    },
    {
        "id": "art1",
        "title": "Статья 1. Принятие условий",
        "content": """1.1. Используя Приложение любым способом, включая запуск, установку, копирование, изучение исходного кода или любое иное использование, Пользователь подтверждает, что прочитал настоящие Условия полностью, понимает их содержание и принимает их в полном объёме без оговорок.

1.2. Если Пользователь не согласен с каким-либо положением настоящих Условий, он должен прекратить использование Приложения и удалить все его копии.

1.3. Принятие Условий фиксируется в диалоговом окне, показываемом при первом запуске (LegalGateDialog), и является обязательным условием дальнейшего использования.

1.4. Принятие Условий не отменяет и не ограничивает права Пользователя по лицензии GNU GPL v3.0.

1.5. Принятие Условий не отменяет императивных прав Пользователя по законодательству о защите прав потребителей его юрисдикции.""",
    },
    {
        "id": "art2",
        "title": "Статья 2. Назначение Приложения",
        "content": """2.1. Приложение — технический инструмент для поиска, каталогизации и воспроизведения аудиовизуального Контента, находящегося в общественном достоянии или распространяемого правообладателями на открытых условиях.

2.2. Приложение изначально ориентировано на открытые архивы (Internet Archive и аналогичные), публикующие Контент на условиях, допускающих его свободное воспроизведение и распространение.

2.3. Приложение не является средством доступа к Контенту, распространение которого нарушает применимое право.

2.4. Назначение Приложения ограничено функциями, перечисленными в документации проекта. Использование Приложения вне этих функций не поддерживается Разработчиком.

2.5. Приложение не предназначено для обхода технических мер защиты или иных средств контроля доступа.""",
    },
    {
        "id": "art3",
        "title": "Статья 3. Характер Приложения",
        "content": """3.1. Приложение не содержит, не хранит постоянно, не распространяет и не передаёт третьим лицам сами аудиовизуальные произведения или их фрагменты.

3.2. Приложение не является хостингом, файлообменным сервисом, BitTorrent-трекером или иным сервисом, предоставляющим доступ к произведениям. Приложение — это клиентское программное обеспечение, установленное на Устройстве Пользователя.

3.3. Всё взаимодействие с Источниками Контента происходит напрямую с Устройства Пользователя. Разработчик не выступает посредником, агентом или оператором таких взаимодействий.

3.4. Приложение не осуществляет предварительный просмотр, модерацию или фильтрацию Контента, получаемого из Источников.

3.5. Технические механизмы Приложения (включая стриминг через BitTorrent-свармы открытых архивов) используются исключительно для эффективной доставки Контента, опубликованного самими Источниками.

3.6. Приложение не является средством обхода блокировок, введённых уполномоченными органами.""",
    },
    {
        "id": "art4",
        "title": "Статья 4. Источники по умолчанию",
        "content": """4.1. По умолчанию Приложение настроено на работу с публичными архивами (Internet Archive и аналогичными), встроенный список которых ограничен Контентом, находящимся в общественном достоянии или распространяемым на законных основаниях.

4.2. Internet Archive и аналогичные архивы самостоятельно определяют правовой статус публикуемых ими материалов.

4.3. Разработчик не гарантирует, что каждый элемент Контента, доступный через Источник по умолчанию, находится в общественном достоянии в юрисдикции Пользователя.

4.4. Оценка правового статуса конкретного произведения остаётся за Пользователем. Разработчик не предоставляет юридических консультаций и не проводит юридическую экспертизу Контента.

4.5. Приложение не проверяет автоматически лицензии или правовой статус Контента, получаемого из Источников по умолчанию.""",
    },
    {
        "id": "art5",
        "title": "Статья 5. Пользовательские источники",
        "content": """5.1. Приложение позволяет Пользователю добавлять собственные Источники через конфигурационный файл data/sources.txt по своему усмотрению.

5.2. Пользователь самостоятельно заполняет конфигурационные файлы и несёт полную ответственность за:
     - содержание добавленных Источников;
     - законность их использования в юрисдикции Пользователя;
     - любые последствия такого использования.

5.3. Разработчик не проверяет, не контролирует и не одобряет содержание пользовательских источников, не имеет к ним доступа и не может нести за них ответственность.

5.4. Пользовательские источники не входят в состав Приложения и не поставляются вместе с ним.

5.5. Пользователь обязуется не добавлять в конфигурационные файлы ссылки на Источники, через которые Контент распространяется с нарушением применимого права.

5.6. Разработчик вправе в любое время прекратить поддержку функции пользовательских источников без предварительного уведомления.""",
    },
    {
        "id": "art6",
        "title": "Статья 6. Внешние программы",
        "content": """6.1. Приложение совместимо с некоторыми Внешними программами, которые Пользователь устанавливает самостоятельно. Типичный пример — внешний индексатор контента, например Jackett.

6.2. Внешние программы:
     - не входят в состав Приложения;
     - не поставляются вместе с Приложением;
     - не разрабатываются и не поддерживаются Разработчиком;
     - распространяются под собственными лицензиями;
     - используются Пользователем на его собственный риск.

6.3. Разработчик не несёт ответственности за Контент, к которому предоставляют доступ Внешние программы, за их работу, за уязвимости в них и за любые последствия их использования.

6.4. Пользователь обязуется самостоятельно ознакомиться с лицензиями и условиями использования Внешних программ перед их установкой и запуском.

6.5. Упоминание Внешней программы в документации Приложения не является рекомендацией, одобрением или гарантией её работоспособности, безопасности или законности.""",
    },
    {
        "id": "art7",
        "title": "Статья 7. Обязанности Пользователя",
        "content": """7.1. Пользователь обязуется использовать Приложение исключительно в законных целях и в соответствии с законодательством своей юрисдикции.

7.2. Пользователь обязуется не использовать Приложение для:
     - распространения, публичного показа или иного использования произведений без согласия правообладателя;
     - обхода технических мер защиты, если такой обход запрещён применимым правом;
     - распространения вредоносного программного обеспечения;
     - нарушения прав третьих лиц;
     - любой иной деятельности, запрещённой законом.

7.3. Пользователь обязуется не добавлять в конфигурационные файлы ссылки на Источники, через которые Контент распространяется с нарушением применимого права.

7.4. Ответственность за соблюдение законов юрисдикции Пользователя лежит исключительно на Пользователе.

7.5. Пользователь несёт единоличную ответственность за безопасность своего Устройства, своих учётных данных и иных ресурсов, используемых вместе с Приложением.""",
    },
    {
        "id": "art8",
        "title": "Статья 8. Интеллектуальная собственность",
        "content": """8.1. Приложение распространяется под лицензией GNU General Public License v3.0. Условия лицензирования изложены в файле LICENSE, поставляемом с Приложением.

8.2. Настоящие Условия не ограничивают права, предоставленные Пользователю этой лицензией, и не налагают дополнительных ограничений на использование кода Приложения сверх установленных лицензией.

8.3. Права на Контент, полученный через Приложение, принадлежат соответствующим правообладателям либо Контент находится в общественном достоянии в соответствии с применимым правом.

8.4. Разработчик не заявляет прав на Контент, полученный через Приложение.

8.5. Название «Amagi-Player», логотип и иные средства индивидуализации проекта не могут использоваться способами, вводящими в заблуждение относительно происхождения Приложения или его связи с Разработчиком.""",
    },
    {
        "id": "art9",
        "title": "Статья 9. Отказ от гарантий",
        "content": """9.1. Приложение предоставляется на условиях «как есть» и «как доступно», без гарантий любого рода, явных или подразумеваемых, включая гарантии товарной пригодности, пригодности для конкретной цели и ненарушения прав третьих лиц.

9.2. Разработчик не гарантирует:
     - бесперебойную или безошибочную работу Приложения;
     - пригодность Приложения для конкретных целей Пользователя;
     - совместимость с аппаратным обеспечением, программным обеспечением или Источниками Пользователя;
     - сохранность данных, истории просмотров или настроек;
     - доступность или правовой статус Контента, получаемого через Источники;
     - работоспособность Внешних программ и пользовательских источников;
     - отсутствие ошибок, уязвимостей или вредоносного кода в зависимостях Приложения.

9.3. Разработчик вправе изменять, приостанавливать или прекращать поддержку Приложения в любое время без предварительного уведомления.

9.4. Пользователь самостоятельно оценивает риски использования Приложения и принимает все связанные с этим риски.

9.5. Положения настоящей Статьи применяются в максимально допустимой применимым правом степени и не ограничивают императивных прав Пользователя по законодательству о защите прав потребителей.""",
    },
    {
        "id": "art10",
        "title": "Статья 10. Ограничение ответственности",
        "content": """10.1. В максимально допустимой применимым правом степени Разработчик не несёт ответственности за:
      - любые прямые, косвенные, случайные, специальные, штрафные или последующие убытки;
      - потерю данных, прибыли, репутации или деловой информации;
      - ущерб, возникший в результате использования или невозможности использования Приложения;
      - действия Пользователя, связанные с использованием Приложения;
      - действия третьих лиц, включая правообладателей, операторов Источников и разработчиков Внешних программ;
      - Контент, полученный через Источники;
      - последствия использования пользовательских источников и Внешних программ.

10.2. Пользователь использует Приложение на свой риск и самостоятельно оценивает правовые последствия такого использования в своей юрисдикции.

10.3. Настоящее ограничение ответственности применяется в максимально допустимой применимым правом степени. Если какое-либо ограничение будет признано недействительным, это не влечёт недействительности остальных ограничений.

10.4. Разработчик не предоставляет юридических консультаций и не проводит юридическую экспертизу Контента, Источников или Внешних программ.

10.5. Настоящая Статья не ограничивает ответственность Разработчика в случаях, когда такая ответственность не может быть ограничена императивными нормами применимого права.""",
    },
    {
        "id": "art11",
        "title": "Статья 11. Обработка данных",
        "content": """11.1. Обработка данных Пользователя регулируется Политикой конфиденциальности, публикуемой в репозитории проекта и показываемой при первом запуске Приложения.

11.2. Политика конфиденциальности образует неотъемлемую часть настоящих Условий.

11.3. В случае противоречия в части обработки данных применяется Политика конфиденциальности.

11.4. Обработка данных осуществляется в соответствии с применимым законодательством о защите данных и иными применимыми нормами.""",
    },
    {
        "id": "art12",
        "title": "Статья 12. Изменения Условий",
        "content": """12.1. Разработчик вправе изменять настоящие Условия.

12.2. Актуальная версия публикуется в репозитории проекта.

12.3. Изменения, затрагивающие права или обязанности Пользователя, фиксируются в Changelog в конце документа.

12.4. Продолжение использования Приложения после публикации изменений означает принятие новой версии Условий.

12.5. В случае существенных изменений Разработчик вправе потребовать повторного принятия Условий при следующем запуске Приложения.""",
    },
    {
        "id": "art13",
        "title": "Статья 13. Применимое право и разрешение споров",
        "content": """13.1. Настоящие Условия регулируются в соответствии с принципами, общепринятыми для open-source проектов, без привязки к какой-либо конкретной национальной правовой системе.

13.2. В случае спора стороны обязуются сначала попытаться разрешить его путём переговоров.

13.3. Если спор не разрешён путём переговоров, он разрешается в порядке, предусмотренном применимым правом.

13.4. Настоящие Условия не ограничивают прав Пользователя, предоставленных императивными нормами законодательства его юрисдикции, включая права потребителей.""",
    },
    {
        "id": "art14",
        "title": "Статья 14. Заключительные положения",
        "content": """14.1. Если какое-либо положение настоящих Условий будет признано недействительным или неисполнимым, это не влечёт недействительности остальных положений.

14.2. Настоящие Условия вступают в силу при первом запуске Приложения Пользователем.

14.3. Настоящие Условия действуют бессрочно до замены новой версией.

14.4. Настоящие Условия составлены на английском языке. Переводы на другие языки, если таковые имеются, носят справочный характер; в случае расхождений преимущественную силу имеет английская версия.""",
    },
    {
        "id": "art15",
        "title": "Статья 15. Контакты",
        "content": """15.1. Вопросы по настоящим Условиям направляются через систему Issues репозитория:
https://github.com/AkashaForge/ama-gi-player/issues

15.2. Разработчик не предоставляет юридических консультаций и не рассматривает индивидуальные юридические вопросы Пользователей.""",
    },
    {
        "id": "art16",
        "title": "Статья 16. Связь с GPLv3",
        "content": """16.1. Приложение распространяется под лицензией GNU General Public License v3.0.

16.2. В случае противоречия между настоящими Условиями и лицензией GPLv3 в части прав на использование, изменение и распространение исходного кода применяется лицензия GPLv3.

16.3. Настоящие Условия не являются дополнительным ограничением на использование кода Приложения сверх установленного GPLv3.""",
    },
    {
        "id": "annexA",
        "title": "Приложение A. Распределение ответственности",
        "content": """A.1. Матрица ответственности по сторонам и предметам:

     +------------------+------------------------------+
     | Предмет          | Ответственная сторона        |
     +------------------+------------------------------+
     | Работоспособность| Разработчик (в рамках GPLv3, |
     | кода Приложения  | «как есть»)                  |
     +------------------+------------------------------+
     | Правовой статус  | Владелец Источника           |
     | Контента в       |                              |
     | Источнике        |                              |
     +------------------+------------------------------+
     | Выбор Источников | Пользователь                 |
     +------------------+------------------------------+
     | Соблюдение       | Пользователь                 |
     | законов          |                              |
     | юрисдикции       |                              |
     +------------------+------------------------------+
     | Установка и      | Пользователь                 |
     | использование    |                              |
     | Внешних программ |                              |
     +------------------+------------------------------+
     | Безопасность     | Разработчик Внешней          |
     | Внешней программы| программы                    |
     +------------------+------------------------------+
     | Сохранность      | Пользователь (ОС, шифрование |
     | данных на        | диска, резервные копии)      |
     | Устройстве       |                              |
     +------------------+------------------------------+
     | Сетевые запросы  | Владелец Источника           |
     | к Источникам     |                              |
     +------------------+------------------------------+

A.2. Разработчик не осуществляет контроль над:
     - содержанием Источников;
     - доступностью Источников;
     - политиками конфиденциальности Источников;
     - работой Внешних программ;
     - конфигурацией Устройства Пользователя.""",
    },
    {
        "id": "annexB",
        "title": "Приложение B. Глоссарий правовых режимов",
        "content": """B.1. Общественное достояние: правовой статус, при котором произведение не охраняется авторским правом либо срок охраны истёк. Точные условия определяются законодательством соответствующей юрисдикции.

B.2. Открытые лицензии: семейство публичных лицензий, позволяющих правообладателю заранее определить условия использования произведения (атрибуция, некоммерческое использование, запрет производных и т. п.).

B.3. Открытый доступ: режим свободного доступа к научным и образовательным материалам, при котором правообладатель разрешает свободное чтение, скачивание и распространение произведения.

B.4. Иные открытые режимы: прочие лицензии и режимы, допускающие свободное воспроизведение и распространение произведения на условиях, установленных правообладателем.

B.5. Пользователь самостоятельно определяет, попадает ли конкретное произведение под один из перечисленных режимов в его юрисдикции.""",
    },
    {
        "id": "annexC",
        "title": "Приложение C. Связь с применимым правом",
        "content": """C.1. Настоящие Условия составлены с должным учётом общих принципов законодательства об авторском праве и смежных правах, законодательства о защите прав потребителей и законодательства о защите данных, действующих в различных юрисдикциях.

C.2. Разработчик не осуществляет деятельности, противоречащей императивным нормам применимого права.

C.3. В отношении прав на использование, изменение и распространение исходного кода Приложения применяется лицензия GNU GPL v3.0.

C.4. В отношении обработки данных применяется Политика конфиденциальности, публикуемая в репозитории проекта.

C.5. В случае противоречия между настоящими Условиями и императивными нормами применимого права применяются соответствующие императивные нормы.

C.6. Пользователь самостоятельно определяет, соответствует ли его использование Приложения требованиям его юрисдикции.""",
    },
    {
        "id": "changelog",
        "title": "Changelog",
        "content": """Версия 1.0 | 2026-01-01 | Первая публикация.
                          Многоуровневая структура,
                          Статьи 1–16, Приложения A–C.

Amagi-Player · Условия использования v1.0 · 2026-01-01""",
    },
]
# ============================================================================
#  3. PRIVACY — Privacy Policy (English) v2.0
# ============================================================================

PRIVACY_TITLE = "Privacy Policy"
PRIVACY_VERSION = "2.0"
PRIVACY_DATE = "2026-10-28"

PRIVACY_SECTIONS = [
    {
        "id": "doc",
        "title": "0. About this document",
        "content": """0.1. This document is the privacy policy (Data Protection Notice) of the Amagi-Player software and is published in the project repository.

0.2. It follows the layered-notice model recommended by Art. 12(7) GDPR: short summary, overview table, full text, technical annexes.

0.3. It forms an integral whole with the Terms of Use. In case of conflict regarding data processing, this Policy applies.

0.4. This Policy has been drafted with reference to:
     - European Union: GDPR (2016/679);
     - United States: COPPA; CCPA/CPRA (California); VCDPA (Virginia); CPA (Colorado); CTDPA (Connecticut);
     - Russian Federation: 152-FZ "On Personal Data".

0.5. Because the Application processes no personal data on Developer-controlled infrastructure (§3), none of the above regimes imposes obligations on the Developer; references are provided for transparency.""",
    },
    {
        "id": "defs",
        "title": "1. Definitions",
        "content": """1.1. "Application" — Amagi-Player, distributed under GNU GPL v3.0.

1.2. "Developer" — the person developing and publishing the Application (AkashaForge). Not a controller or operator of User's personal data.

1.3. "User" — a natural person using the Application on their own device.

1.4. "Device" — the User's hardware.

1.5. "Source" — an external service the Application contacts for content or metadata (Internet Archive, Kinopoisk API, user-defined sources, local indexers).

1.6. "Personal data" — info relating to an identified or identifiable natural person (GDPR Art. 4(1); 152-FZ Art. 3).

1.7. "Processing" — any operation on personal data.

1.8. "Local data" — data created and stored by the Application exclusively on the User's Device, under the User's sole control.""",
    },
    {
        "id": "scope",
        "title": "2. Scope",
        "content": """2.1. Within scope:
     - processing of Local data by the Application;
     - network requests initiated by the Application;
     - configuration files created or modified by the User
       (data/mode.txt, data/sources.txt, .env);
     - diagnostic console output.

2.2. Outside scope:
     - processing by the Device's operating system;
     - processing by Sources (per their own policies);
     - processing by third-party programs installed by the User;
     - processing on GitHub's side.""",
    },
    {
        "id": "roles",
        "title": "3. Roles and responsibilities",
        "content": """3.1. The Developer does not act as a controller, processor, or operator of the User's personal data, because:
     - the Developer does not receive the User's personal data;
     - the Developer has no technical means of accessing the Device;
     - the Developer does not process personal data on behalf of the User.

3.2. The User is the sole party controlling the processing of Local data. Under 152-FZ the User is the operator of any personal data in .env.

3.3. Interaction with Sources is governed by the policies of those Sources. The Developer is not a party to those relationships.""",
    },
    {
        "id": "lawful",
        "title": "4. Lawful basis and principles",
        "content": """4.1. Processing of Local data is carried out solely for the Application's operation, on the basis of the User's consent given on first launch (GDPR Art. 6(1)(a); 152-FZ Art. 9), and for performance of the agreement on use (GDPR Art. 6(1)(b)).

4.2. Principles:
     - minimization (GDPR Art. 5(1)(c); 152-FZ Art. 5);
     - storage limitation (GDPR Art. 5(1)(e));
     - transparency (GDPR Art. 5(1)(a); 152-FZ Art. 18);
     - integrity and confidentiality (GDPR Art. 5(1)(f));
     - accountability (GDPR Art. 5(2)).

4.3. Because the Developer does not process personal data, obligations under GDPR Art. 30 and 152-FZ Art. 22 do not apply.""",
    },
    {
        "id": "inventory",
        "title": "5. Categories of processed data",
        "content": """5.1. Categories of Local data:

     #1. Watch history
         Format: SQLite (data/app_data.db, table user_history)
         Purpose: "Continue watching"
         Retention: until deleted by User

     #2. Poster cache
         Format: JPEG/PNG (data/cache/{kp_id}.jpg)
         Purpose: UI performance
         Retention: until deleted by User

     #3. Metadata cache
         Format: JSON (data/cache/short/, full/, lists/)
         Purpose: reduce network requests
         Retention: until deleted by User

     #4. Film catalog
         Format: SQLite (data/whitelist.db, from bundled whitelist_seed.db)
         Purpose: feed of public-domain films
         Retention: bundled with Application; recreated from seed

     #5. Mode selection
         Format: plain text (data/mode.txt)
         Purpose: mode choice (public/private)
         Retention: until deleted by User

     #6. Source list
         Format: plain text (data/sources.txt)
         Purpose: user-defined sources
         Retention: until file is deleted

     #7. API keys
         Format: plain text (.env next to executable)
         Purpose: optional access to Kinopoisk API
         Retention: until deleted by User

     #8. Diagnostic output
         Format: console (stderr), not persisted
         Purpose: diagnostics
         Retention: not stored

5.2. None of these categories is transmitted to the Developer or to third parties on the Developer's behalf.

5.3. config.py is a read-only source-code module with default parameters. It is not a data store and contains no User data.

5.4. Full technical specification — Annex A.""",
    },
    {
        "id": "not_processed",
        "title": "6. Categories that are not processed",
        "content": """6.1. NOT processed:
     - name, surname, email, phone, postal address;
     - credentials (logins, passwords, access tokens) — partial exception in 6.2;
     - payment information;
     - biometric data;
     - geolocation (GPS, IP geolocation);
     - contacts, files, messages from the Device;
     - usage analytics;
     - telemetry, crash reports;
     - advertising identifiers;
     - fingerprinting data.

6.2. API key (exception to credentials): an optional Kinopoisk API key may be stored in .env. It is not a credential for any Developer-held account; it identifies the User only to kinopoiskapiunofficial.tech and is transmitted only to that service, only when the User triggers a metadata request, and only in private mode. The Developer never receives this key.

6.3. The Application contains no analytics, advertising, telemetry, crash-reporting, or A/B-testing modules.""",
    },
    {
        "id": "network",
        "title": "7. Network interactions",
        "content": """7.1. Network requests are initiated solely to obtain content and metadata from Sources chosen by the User.

7.2. Typical interactions:

     #1. Internet Archive (archive.org)
         Trigger: search, playback
         Transmits: IP address, User-Agent, HTTP headers, search query

     #2. Kinopoisk API (kinopoiskapiunofficial.tech)
         Trigger: optional, only if KP_API_KEY is set AND private mode
         Transmits: IP address, User-Agent, API key, film identifier

     #3. User-defined sources (data/sources.txt)
         Trigger: search over user sources
         Transmits: IP address, User-Agent, HTTP headers, search query

     #4. Local external indexer (127.0.0.1)
         Trigger: if indexer is installed by User
         Transmits: local HTTP request

     #5. BitTorrent swarms of Internet Archive
         Trigger: playback in private mode only
         Transmits: IP address, port, BitTorrent peer-id

7.3. Transmission of IP address, User-Agent, and HTTP headers is an inherent property of HTTP and is not the result of any data collection by the Developer.

7.4. The Developer does not control data processing by Sources and is not responsible for such processing.

7.5. Users for whom additional privacy matters may apply standard OS or network-layer tools at their own discretion. The Application neither requires nor configures such tools automatically.

7.6. Full specification of endpoints — Annex B.""",
    },
    {
        "id": "third_parties",
        "title": "8. Third parties and sub-processors",
        "content": """8.1. The Developer does not engage processors or sub-processors to process the User's personal data.

8.2. The Developer does not transfer Local data to third parties.

8.3. The Developer does not perform any international transfer of the User's personal data, because it does not receive such data.""",
    },
    {
        "id": "retention",
        "title": "9. Retention",
        "content": """9.1. The retention period for Local data is unlimited and is determined solely by the User.

9.2. Local data is erased:
     - through Application settings (cleanup function);
     - manually — by deleting the corresponding files and folders;
     - when the Application is removed from the Device.

9.3. Once deleted, Local data cannot be restored by the Application's own means.""",
    },
    {
        "id": "security",
        "title": "10. Security measures",
        "content": """10.1. Protections applied by the Application:
      - no network transmission of Local data to the Developer's servers;
      - no remote access to the Device by the Developer;
      - isolation of child processes (FFmpeg, headless browser) with lifetime control;
      - no built-in remote-control mechanisms.

10.2. Protection at the OS level (disk encryption, privilege separation, antivirus) is the User's responsibility.

10.3. Because the Developer does not process personal data, obligations under GDPR Art. 32 and 152-FZ Art. 19 do not apply. The measures in 10.1 are applied voluntarily.""",
    },
    {
        "id": "rights",
        "title": "11. Rights of the data subject",
        "content": """11.1. Rights with respect to Local data:

      #1. Access           (GDPR 15; 152-FZ 14) — open the application folder
      #2. Rectification    (GDPR 16; 152-FZ 20) — edit files manually
      #3. Erasure          (GDPR 17; 152-FZ 21) — settings → cleanup, or manually
      #4. Restriction      (GDPR 18; 152-FZ 16) — delete the corresponding files
      #5. Portability      (GDPR 20; 152-FZ 20) — copy the Local data files
      #6. Object           (GDPR 21; 152-FZ 16) — stop using the Application
      #7. Withdraw consent (GDPR 7(3); 152-FZ 9) — uninstall the Application
      #8. Lodge a complaint (GDPR 77; 152-FZ 23-24) — contact the supervisory authority

11.2. Because the Developer does not receive Local data, rights 1–7 are exercised directly on the Device.

11.3. Under CCPA/CPRA (California), VCDPA (Virginia), CPA (Colorado), CTDPA (Connecticut), the User has analogous rights (to know, delete, correct, opt out of sale or sharing). Because the Developer does not sell or share data and does not receive it, these rights are exercised locally.

11.4. The right under 11.1.8 is exercised per the law of the User's jurisdiction (in Russia — 152-FZ Art. 23).""",
    },
    {
        "id": "children",
        "title": "12. Children",
        "content": """12.1. The Application is not intended for persons below the age at which, under their jurisdiction's law, they can independently consent to the processing of personal data (GDPR Art. 8; COPPA — under 13; 152-FZ — under 18 unless otherwise provided).

12.2. The Developer does not knowingly collect or process data of persons below that age.

12.3. Parents or guardians who believe that a minor is using the Application without proper consent may uninstall the Application from the Device.""",
    },
    {
        "id": "changes",
        "title": "13. Changes to this Policy",
        "content": """13.1. The Developer may amend this Policy.

13.2. The current version is published in the project repository.

13.3. Changes affecting categories of processed data, network interactions, or User rights are recorded in the Changelog.

13.4. Continued use after changes are published constitutes acceptance of the new version.""",
    },
    {
        "id": "contacts",
        "title": "14. Contact",
        "content": """14.1. Questions concerning this Policy: repository Issues system:
https://github.com/AkashaForge/ama-gi-player/issues

14.2. The Developer does not hold the User's personal data, so requests for access, rectification, erasure, or portability need not be addressed to the Developer (see 11.2).""",
    },
    {
        "id": "annexA",
        "title": "Annex A. Technical data inventory",
        "content": """A.1. Watch history
     File:      data/app_data.db
     Format:    SQLite 3 (WAL)
     Table:     user_history
     Fields:    kp_id INTEGER, movie_title TEXT,
                current_seconds REAL, duration_sec REAL,
                updated_at TIMESTAMP
     Transfer:  none

A.2. Poster cache
     Folder:    data/cache/
     Format:    JPEG, PNG
     Naming:    {kp_id}.jpg
     Transfer:  none

A.3. Metadata cache
     Folders:   data/cache/short/, data/cache/full/, data/cache/lists/
     Format:    JSON
     Naming:    {id}.json (short/full), {hash}.json (lists)
     Populated: only when Kinopoisk API is used (private mode)
     Transfer:  none

A.4. Film catalog
     File:      data/whitelist.db (working), data/whitelist_seed.db (bundled)
     Format:    SQLite 3
     Table:     movie_whitelist
     User data: no (public-domain metadata)
     Transfer:  none

A.5. Mode selection
     File:      data/mode.txt
     Format:    plain text (public | private)
     User data: no (preference only)
     Transfer:  none

A.6. Source list
     File:      data/sources.txt
     Format:    plain text, one record per line
     Schema:    <type>|<base_url>|<display_name>
     Transfer:  only as HTTP requests to the listed sources

A.7. API keys
     File:      .env (next to executable)
     Format:    plain text, KEY=value
     Fields:    KP_API_KEY, ARIA2_SECRET
     Personal data: KP_API_KEY identifies the User to Kinopoisk API
     Transfer:  KP_API_KEY -> kinopoiskapiunofficial.tech only, private mode only
     Retention: until deleted by User

A.8. Configuration defaults
     File:      config.py
     Format:    Python source code (read-only module)
     User data: none
     Transfer:  none

A.9. Diagnostics
     Output:    console (stderr)
     Persisted: no by default
     Personal data: none (see Annex C)""",
    },
    {
        "id": "annexB",
        "title": "Annex B. Network endpoints",
        "content": """B.1. Internet Archive
     Host:      archive.org, *.archive.org
     Protocol:  HTTPS
     Endpoints: /advancedsearch.php, /metadata/<id>,
                /download/<id>/<file>, /services/img/<id>
     Headers:   User-Agent: Amagi-Player/<version>, Accept, Accept-Language
     Trigger:   search, card, playback

B.2. Kinopoisk API
     Host:      kinopoiskapiunofficial.tech
     Protocol:  HTTPS
     Endpoints: /api/v2.1/films/search-by-keyword, /api/v2.2/films/<id>
     Headers:   X-API-KEY: <KP_API_KEY>, User-Agent: Amagi-Player/<version>, Accept
     Trigger:   private mode only when KP_API_KEY is set

B.3. User-defined sources
     Host:      determined by data/sources.txt
     Protocol:  HTTPS (recommended), HTTP
     Endpoints: determined by the source type
     Headers:   User-Agent: Amagi-Player/<version>, Accept
     Trigger:   search over user sources

B.4. Local external indexer
     Host:      127.0.0.1, localhost
     Protocol:  HTTP
     Endpoints: determined by the indexer configuration
     Headers:   standard HTTP
     Trigger:   if the User connects an indexer

B.5. BitTorrent swarms of Internet Archive
     Protocol:  BitTorrent (libtorrent)
     Trackers:  public trackers from the Internet Archive .torrent file
     Transmits: IP address, port, BitTorrent peer-id
     Trigger:   playback in private mode only""",
    },
    {
        "id": "annexC",
        "title": "Annex C. Logging specification",
        "content": """C.1. Diagnostics go only to console (stderr). No persistent log files are created by default.

C.2. NOT written to diagnostics:
     - IP addresses of Sources;
     - the User's search queries;
     - HTTP header contents;
     - personal data, including API keys.

C.3. Written to diagnostics:
     - timestamps;
     - logging levels;
     - module identifiers;
     - error messages and stack traces.

C.4. Diagnostics are not transmitted to the Developer and are not sent to any network endpoint.

C.5. If the User enables file logging, location and retention are determined by that configuration; the Developer does not receive these logs.""",
    },
    {
        "id": "annexD",
        "title": "Annex D. Compliance matrix",
        "content": """EU (GDPR):
  Art. 5    principles              applicable (reference)  complied (section 4)
  Art. 6    lawful basis            applicable (reference)  consent + agreement (4.1)
  Art. 12(7) layered notice         applicable (reference)  document structure implements it
  Art. 13-14 information            applicable (reference)  sections 5-9
  Art. 15-21 data subject rights    applicable (reference)  section 11
  Art. 30   records                 not applicable          Developer is not a controller (3.1)
  Art. 32   security                not applicable          no processing (10.3)
  Art. 44-49 transfers              not applicable          no transfer (8.3)

United States:
  COPPA (15 U.S.C. 6501-6506)       applicable              section 12
  CCPA/CPRA (California)            applicable              rights exercised locally (11.3)
  VCDPA (Virginia)                  applicable              analogous to CCPA (11.3)
  CPA (Colorado)                    applicable              analogous to CCPA (11.3)
  CTDPA (Connecticut)               applicable              analogous to CCPA (11.3)

Russian Federation (152-FZ):
  Art. 3    definitions             applicable (reference)  section 1
  Art. 5    principles              applicable (reference)  section 4.2
  Art. 9    consent                 applicable (reference)  section 4.1
  Art. 14   access                  applicable (reference)  section 11.1
  Art. 18   informing               applicable (reference)  sections 5-9
  Art. 19   security                not applicable          no processing (10.3)
  Art. 22   notification            not applicable          not an operator (3.1)
  Art. 12   cross-border transfer   not applicable          no transfer (8.3)

Reference only:
  LGPD (Brazil)                     applicable (reference)  analogous to GDPR
  PIPL (China)                      not applicable          not a processor""",
    },
    {
        "id": "changelog",
        "title": "Changelog",
        "content": """Version 1.0 | 2026-01-01 | Initial publication.
Version 2.0 | 2026-10-28 | Corrected data inventory to real file paths
                           (data/app_data.db, data/cache/, .env);
                           removed fictitious config.json and
                           cache/metadata.db; added .env, data/mode.txt,
                           data/whitelist.db, data/sources.txt; clarified
                           config.py is source code, no user data;
                           added Kinopoisk API endpoint (B.2); explicit
                           API key disclosure (6.2); US state laws and
                           152-FZ in compliance matrix; removed file log
                           rotation (console-only by default).

Amagi-Player · Privacy Policy v2.0 · 2026-10-28""",
    },
]


# ============================================================================
#  4. PRIVACY — Политика конфиденциальности (Русский) v2.0
# ============================================================================

PRIVACY_TITLE_RU = "Политика конфиденциальности"
PRIVACY_VERSION_RU = "2.0"
PRIVACY_DATE_RU = "2026-10-28"

PRIVACY_SECTIONS_RU = [
    {
        "id": "doc",
        "title": "0. О настоящем документе",
        "content": """0.1. Настоящий документ является политикой конфиденциальности (Уведомлением о защите данных) программного обеспечения Amagi-Player и публикуется в репозитории проекта.

0.2. Документ следует модели многоуровневого уведомления, рекомендованной ст. 12(7) GDPR: краткое резюме, обзорная таблица, полный текст, технические приложения.

0.3. Документ образует единое целое с Условиями использования. В случае противоречия в части обработки данных применяется настоящая Политика.

0.4. Документ составлен с учётом:
     - Европейский союз: GDPR (2016/679);
     - США: COPPA; CCPA/CPRA (Калифорния); VCDPA (Вирджиния); CPA (Колорадо); CTDPA (Коннектикут);
     - Россия: 152-ФЗ «О персональных данных».

0.5. Поскольку Приложение не обрабатывает персональные данные на инфраструктуре Разработчика (§3), ни один из режимов не создаёт обязанностей для Разработчика; ссылки приведены для прозрачности.""",
    },
    {
        "id": "defs",
        "title": "1. Определения",
        "content": """1.1. «Приложение» — Amagi-Player, распространяемое под GNU GPL v3.0.

1.2. «Разработчик» — лицо, разрабатывающее и публикующее Приложение (AkashaForge). Не является контролёром или оператором персональных данных Пользователя.

1.3. «Пользователь» — физическое лицо, использующее Приложение на своём устройстве.

1.4. «Устройство» — аппаратное обеспечение Пользователя.

1.5. «Источник» — внешний сервис, к которому Приложение обращается за контентом или метаданными (Internet Archive, API Кинопоиска, пользовательские источники, локальные индексаторы).

1.6. «Персональные данные» — информация, относящаяся к идентифицированному или идентифицируемому лицу (GDPR ст. 4(1); 152-ФЗ ст. 3).

1.7. «Обработка» — любая операция с персональными данными.

1.8. «Локальные данные» — данные, создаваемые и хранимые Приложением исключительно на Устройстве Пользователя, под полным контролем Пользователя.""",
    },
    {
        "id": "scope",
        "title": "2. Область действия",
        "content": """2.1. В область действия входит:
     - обработка Локальных данных Приложением;
     - сетевые запросы Приложения;
     - конфигурационные файлы (data/mode.txt, data/sources.txt, .env);
     - диагностический вывод в консоль.

2.2. Вне области действия:
     - обработка данных операционной системой;
     - обработка данных Источниками (по их политикам);
     - обработка данных сторонними программами, установленными Пользователем;
     - обработка данных на стороне GitHub.""",
    },
    {
        "id": "roles",
        "title": "3. Роли и ответственность",
        "content": """3.1. Разработчик не выступает контролёром, обработчиком или оператором персональных данных Пользователя, поскольку:
     - не получает персональные данные Пользователя;
     - не имеет технических средств доступа к Устройству;
     - не обрабатывает персональные данные от имени Пользователя.

3.2. Пользователь — единственная сторона, контролирующая обработку Локальных данных. Согласно 152-ФЗ Пользователь является оператором персональных данных в .env.

3.3. Взаимодействие с Источниками регулируется политиками этих Источников. Разработчик не является стороной этих отношений.""",
    },
    {
        "id": "lawful",
        "title": "4. Правовые основания и принципы",
        "content": """4.1. Обработка Локальных данных осуществляется исключительно для функционирования Приложения, на основании согласия Пользователя при первом запуске (GDPR ст. 6(1)(a); 152-ФЗ ст. 9), и для исполнения соглашения (GDPR ст. 6(1)(b)).

4.2. Принципы:
     - минимизация (GDPR ст. 5(1)(c); 152-ФЗ ст. 5);
     - ограничение хранения (GDPR ст. 5(1)(e));
     - прозрачность (GDPR ст. 5(1)(a); 152-ФЗ ст. 18);
     - целостность и конфиденциальность (GDPR ст. 5(1)(f));
     - подотчётность (GDPR ст. 5(2)).

4.3. Поскольку Разработчик не обрабатывает персональные данные, обязанности по GDPR ст. 30 и 152-ФЗ ст. 22 к нему не применяются.""",
    },
    {
        "id": "inventory",
        "title": "5. Категории обрабатываемых данных",
        "content": """5.1. Категории Локальных данных:

     #1. История просмотров
         Формат: SQLite (data/app_data.db, таблица user_history)
         Назначение: «Продолжить просмотр»
         Хранение: до удаления Пользователем

     #2. Кэш постеров
         Формат: JPEG/PNG (data/cache/{kp_id}.jpg)
         Назначение: производительность UI
         Хранение: до удаления Пользователем

     #3. Кэш метаданных
         Формат: JSON (data/cache/short/, full/, lists/)
         Назначение: сокращение сетевых запросов
         Хранение: до удаления Пользователем

     #4. Каталог фильмов
         Формат: SQLite (data/whitelist.db, из whitelist_seed.db)
         Назначение: лента public-domain фильмов
         Хранение: в составе Приложения; пересоздаётся

     #5. Выбор режима
         Формат: plain text (data/mode.txt)
         Назначение: режим (public/private)
         Хранение: до удаления Пользователем

     #6. Список источников
         Формат: plain text (data/sources.txt)
         Назначение: пользовательские источники
         Хранение: до удаления файла

     #7. API-ключи
         Формат: plain text (.env рядом с exe)
         Назначение: опциональный доступ к API Кинопоиска
         Хранение: до удаления Пользователем

     #8. Диагностика
         Формат: консоль (stderr), не сохраняется
         Назначение: диагностика
         Хранение: не хранится

5.2. Ни одна из категорий не передаётся Разработчику или третьим лицам от имени Разработчика.

5.3. config.py — read-only модуль исходного кода с параметрами по умолчанию. Не хранилище данных, пользовательских данных не содержит.

5.4. Полная техническая спецификация — Приложение A.""",
    },
    {
        "id": "not_processed",
        "title": "6. Категории, которые не обрабатываются",
        "content": """6.1. НЕ обрабатываются:
     - имя, фамилия, email, телефон, почтовый адрес;
     - учётные данные (логины, пароли, токены) — частичное исключение в 6.2;
     - платёжная информация;
     - биометрические данные;
     - геолокация (GPS, IP-геолокация);
     - контакты, файлы, сообщения с Устройства;
     - аналитика использования;
     - телеметрия, отчёты о сбоях;
     - рекламные идентификаторы;
     - данные фингерпринтинга.

6.2. API-ключ (исключение из учётных данных): опциональный API-ключ Кинопоиска может храниться в .env. Это не учётные данные аккаунта Разработчика; он идентифицирует Пользователя только перед kinopoiskapiunofficial.tech и передаётся только этому сервису, только когда Пользователь инициирует запрос метаданных, и только в режиме private. Разработчик никогда не получает этот ключ.

6.3. Приложение не содержит модулей аналитики, рекламы, телеметрии, crash-reporting или A/B-тестирования.""",
    },
    {
        "id": "network",
        "title": "7. Сетевые взаимодействия",
        "content": """7.1. Сетевые запросы инициируются исключительно для получения контента и метаданных из Источников, выбранных Пользователем.

7.2. Типичные взаимодействия:

     #1. Internet Archive (archive.org)
         Триггер: поиск, воспроизведение
         Передаёт: IP-адрес, User-Agent, HTTP-заголовки, поисковый запрос

     #2. API Кинопоиска (kinopoiskapiunofficial.tech)
         Триггер: опционально, только если KP_API_KEY задан И режим private
         Передаёт: IP-адрес, User-Agent, API-ключ, идентификатор фильма

     #3. Пользовательские источники (data/sources.txt)
         Триггер: поиск по пользовательским источникам
         Передаёт: IP-адрес, User-Agent, HTTP-заголовки, поисковый запрос

     #4. Локальный внешний индексатор (127.0.0.1)
         Триггер: если индексатор установлен Пользователем
         Передаёт: локальный HTTP-запрос

     #5. BitTorrent-свармы Internet Archive
         Триггер: воспроизведение только в режиме private
         Передаёт: IP-адрес, порт, BitTorrent peer-id

7.3. Передача IP-адреса, User-Agent и HTTP-заголовков — неотъемлемое свойство HTTP и не является результатом сбора данных Разработчиком.

7.4. Разработчик не контролирует обработку данных Источниками и не несёт за неё ответственности.

7.5. Пользователи, для которых важна дополнительная приватность, могут применять стандартные средства ОС или сетевого уровня по своему усмотрению. Приложение не требует и не настраивает такие средства автоматически.

7.6. Полная спецификация эндпоинтов — Приложение B.""",
    },
    {
        "id": "third_parties",
        "title": "8. Третьи стороны и субобработчики",
        "content": """8.1. Разработчик не привлекает обработчиков или субобработчиков для обработки персональных данных Пользователя.

8.2. Разработчик не передаёт Локальные данные третьим лицам.

8.3. Разработчик не осуществляет международную передачу персональных данных Пользователя, поскольку не получает такие данные.""",
    },
    {
        "id": "retention",
        "title": "9. Хранение",
        "content": """9.1. Срок хранения Локальных данных не ограничен и определяется исключительно Пользователем.

9.2. Локальные данные удаляются:
     - через настройки Приложения (функция очистки);
     - вручную — удалением соответствующих файлов и папок;
     - при удалении Приложения с Устройства.

9.3. После удаления Локальные данные не могут быть восстановлены средствами Приложения.""",
    },
    {
        "id": "security",
        "title": "10. Меры безопасности",
        "content": """10.1. Меры, применяемые Приложением:
      - отсутствие сетевой передачи Локальных данных на серверы Разработчика;
      - отсутствие удалённого доступа к Устройству со стороны Разработчика;
      - изоляция дочерних процессов (FFmpeg, headless-браузер) с контролем времени жизни;
      - отсутствие встроенных механизмов удалённого управления.

10.2. Защита на уровне ОС (шифрование диска, разделение привилегий, антивирус) — ответственность Пользователя.

10.3. Поскольку Разработчик не обрабатывает персональные данные, обязанности по GDPR ст. 32 и 152-ФЗ ст. 19 не применяются. Меры в 10.1 применяются добровольно.""",
    },
    {
        "id": "rights",
        "title": "11. Права субъекта данных",
        "content": """11.1. Права в отношении Локальных данных:

      #1. Доступ          (GDPR 15; 152-ФЗ 14) — открыть папку приложения
      #2. Исправление     (GDPR 16; 152-ФЗ 20) — редактировать файлы вручную
      #3. Удаление        (GDPR 17; 152-ФЗ 21) — настройки → очистка, либо вручную
      #4. Ограничение     (GDPR 18; 152-ФЗ 16) — удалить соответствующие файлы
      #5. Переносимость   (GDPR 20; 152-ФЗ 20) — скопировать файлы Локальных данных
      #6. Возражение      (GDPR 21; 152-ФЗ 16) — прекратить использование
      #7. Отзыв согласия  (GDPR 7(3); 152-ФЗ 9) — удалить Приложение
      #8. Подача жалобы   (GDPR 77; 152-ФЗ 23-24) — обратиться в надзорный орган

11.2. Поскольку Разработчик не получает Локальные данные, права 1–7 реализуются Пользователем непосредственно на Устройстве.

11.3. По CCPA/CPRA (Калифорния), VCDPA (Вирджиния), CPA (Колорадо), CTDPA (Коннектикут) Пользователь обладает аналогичными правами (знать, удалять, исправлять, отказываться от продажи или обмена). Поскольку Разработчик не продаёт и не обменивает данные и не получает их, права реализуются локально.

11.4. Право по 11.1.8 реализуется в порядке, установленном законодательством юрисдикции Пользователя (в России — 152-ФЗ ст. 23).""",
    },
    {
        "id": "children",
        "title": "12. Дети",
        "content": """12.1. Приложение не предназначено для лиц, не достигших возраста, с которого согласно законодательству их юрисдикции они могут самостоятельно давать согласие на обработку персональных данных (GDPR ст. 8; COPPA — до 13 лет; 152-ФЗ — до 18 лет, если иное не предусмотрено).

12.2. Разработчик сознательно не собирает и не обрабатывает данные лиц младше этого возраста.

12.3. Родители или опекуны, полагающие, что несовершеннолетний использует Приложение без надлежащего согласия, могут удалить Приложение с Устройства.""",
    },
    {
        "id": "changes",
        "title": "13. Изменения Политики",
        "content": """13.1. Разработчик вправе изменять настоящую Политику.

13.2. Актуальная версия публикуется в репозитории проекта.

13.3. Изменения, затрагивающие категории обрабатываемых данных, сетевые взаимодействия или права Пользователя, фиксируются в Changelog.

13.4. Продолжение использования после публикации изменений означает принятие новой версии.""",
    },
    {
        "id": "contacts",
        "title": "14. Контакты",
        "content": """14.1. Вопросы по настоящей Политике: система Issues репозитория:
https://github.com/AkashaForge/ama-gi-player/issues

14.2. Разработчик не хранит персональные данные Пользователя, поэтому запросы о доступе, исправлении, удалении или переносимости не нужно адресовать Разработчику (см. 11.2).""",
    },
    {
        "id": "annexA",
        "title": "Приложение A. Техническая инвентаризация данных",
        "content": """A.1. История просмотров
     Файл:       data/app_data.db
     Формат:     SQLite 3 (WAL)
     Таблица:    user_history
     Поля:       kp_id INTEGER, movie_title TEXT,
                 current_seconds REAL, duration_sec REAL,
                 updated_at TIMESTAMP
     Передача:   отсутствует

A.2. Кэш постеров
     Папка:      data/cache/
     Формат:     JPEG, PNG
     Имена:      {kp_id}.jpg
     Передача:   отсутствует

A.3. Кэш метаданных
     Папки:      data/cache/short/, data/cache/full/, data/cache/lists/
     Формат:     JSON
     Имена:      {id}.json (short/full), {hash}.json (lists)
     Заполняется: только при использовании API Кинопоиска (режим private)
     Передача:   отсутствует

A.4. Каталог фильмов
     Файл:       data/whitelist.db (рабочая), data/whitelist_seed.db (поставляемая)
     Формат:     SQLite 3
     Таблица:    movie_whitelist
     Данные пользователя: нет (метаданные public-domain)
     Передача:   отсутствует

A.5. Выбор режима
     Файл:       data/mode.txt
     Формат:     plain text (public | private)
     Данные пользователя: нет (только предпочтение)
     Передача:   отсутствует

A.6. Список источников
     Файл:       data/sources.txt
     Формат:     plain text, одна запись на строку
     Схема:      <type>|<base_url>|<display_name>
     Передача:   только в виде HTTP-запросов к указанным источникам

A.7. API-ключи
     Файл:       .env (рядом с exe)
     Формат:     plain text, KEY=value
     Поля:       KP_API_KEY, ARIA2_SECRET
     Персональные данные: KP_API_KEY идентифицирует Пользователя перед API Кинопоиска
     Передача:   KP_API_KEY -> kinopoiskapiunofficial.tech, только в режиме private
     Хранение:   до удаления Пользователем

A.8. Параметры по умолчанию
     Файл:       config.py
     Формат:     Python source code (read-only модуль)
     Данные пользователя: нет
     Передача:   отсутствует

A.9. Диагностика
     Вывод:      консоль (stderr)
     Сохраняется: нет по умолчанию
     Персональные данные: нет (см. Приложение C)""",
    },
    {
        "id": "annexB",
        "title": "Приложение B. Сетевые эндпоинты",
        "content": """B.1. Internet Archive
     Хост:       archive.org, *.archive.org
     Протокол:   HTTPS
     Эндпоинты:  /advancedsearch.php, /metadata/<id>,
                 /download/<id>/<file>, /services/img/<id>
     Заголовки:  User-Agent: Amagi-Player/<version>, Accept, Accept-Language
     Триггер:    поиск, карточка, воспроизведение

B.2. API Кинопоиска
     Хост:       kinopoiskapiunofficial.tech
     Протокол:   HTTPS
     Эндпоинты:  /api/v2.1/films/search-by-keyword, /api/v2.2/films/<id>
     Заголовки:  X-API-KEY: <KP_API_KEY>, User-Agent: Amagi-Player/<version>, Accept
     Триггер:    только режим private при заданном KP_API_KEY

B.3. Пользовательские источники
     Хост:       определяется data/sources.txt
     Протокол:   HTTPS (рекомендуется), HTTP
     Эндпоинты:  определяются типом источника
     Заголовки:  User-Agent: Amagi-Player/<version>, Accept
     Триггер:    поиск по пользовательским источникам

B.4. Локальный внешний индексатор
     Хост:       127.0.0.1, localhost
     Протокол:   HTTP
     Эндпоинты:  определяются конфигурацией индексатора
     Заголовки:  стандартные HTTP
     Триггер:    если Пользователь подключил индексатор

B.5. BitTorrent-свармы Internet Archive
     Протокол:   BitTorrent (libtorrent)
     Трекеры:    публичные трекеры из .torrent-файла Internet Archive
     Передаёт:   IP-адрес, порт, BitTorrent peer-id
     Триггер:    воспроизведение только в режиме private""",
    },
    {
        "id": "annexC",
        "title": "Приложение C. Спецификация журналирования",
        "content": """C.1. Диагностика идёт только в консоль (stderr). Файловые журналы по умолчанию не создаются.

C.2. НЕ записываются:
     - IP-адреса Источников;
     - поисковые запросы Пользователя;
     - содержимое HTTP-заголовков;
     - персональные данные, включая API-ключи.

C.3. Записываются:
     - метки времени;
     - уровни логирования;
     - идентификаторы модулей;
     - сообщения об ошибках и стектрейсы.

C.4. Диагностика не передаётся Разработчику и не отправляется на сетевые эндпоинты.

C.5. Если Пользователь включит файловое логирование, местоположение и срок хранения определяются этой конфигурацией; Разработчик эти логи не получает.""",
    },
    {
        "id": "annexD",
        "title": "Приложение D. Матрица соответствия",
        "content": """ЕС (GDPR):
  ст. 5     принципы                применимо (справочно)   соблюдается (раздел 4)
  ст. 6     правовое основание      применимо (справочно)   согласие + соглашение (4.1)
  ст. 12(7) многоуровневое уведомление применимо (справочно) структура документа
  ст. 13-14 информация             применимо (справочно)   разделы 5-9
  ст. 15-21 права субъекта         применимо (справочно)   раздел 11
  ст. 30    реестр                 не применимо            Разработчик не контролёр (3.1)
  ст. 32    безопасность           не применимо            нет обработки (10.3)
  ст. 44-49 передача               не применимо            нет передачи (8.3)

США:
  COPPA (15 U.S.C. 6501-6506)      применимо               раздел 12
  CCPA/CPRA (Калифорния)           применимо               права реализуются локально (11.3)
  VCDPA (Вирджиния)                применимо               аналогично CCPA (11.3)
  CPA (Колорадо)                   применимо               аналогично CCPA (11.3)
  CTDPA (Коннектикут)              применимо               аналогично CCPA (11.3)

Россия (152-ФЗ):
  ст. 3     определения            применимо (справочно)   раздел 1
  ст. 5     принципы               применимо (справочно)   раздел 4.2
  ст. 9     согласие               применимо (справочно)   раздел 4.1
  ст. 14    доступ                 применимо (справочно)   раздел 11.1
  ст. 18    информирование         применимо (справочно)   разделы 5-9
  ст. 19    безопасность           не применимо            нет обработки (10.3)
  ст. 22    уведомление            не применимо            не оператор (3.1)
  ст. 12    трансграничная передача не применимо           нет передачи (8.3)

Справочно:
  LGPD (Бразилия)                  применимо (справочно)   аналогично GDPR
  PIPL (Китай)                     не применимо            не обработчик""",
    },
    {
        "id": "changelog",
        "title": "Changelog",
        "content": """Версия 1.0 | 2026-01-01 | Первая публикация.
Версия 2.0 | 2026-10-28 | Инвентаризация приведена к реальным путям
                           (data/app_data.db, data/cache/, .env);
                           удалены фиктивные config.json и
                           cache/metadata.db; добавлены .env,
                           data/mode.txt, data/whitelist.db,
                           data/sources.txt; уточнено, что config.py —
                           исходный код без пользовательских данных;
                           добавлен эндпоинт API Кинопоиска (B.2);
                           явное раскрытие API-ключа (6.2); законы
                           штатов США и 152-ФЗ в матрице; удалена
                           файловая ротация логов (консоль).

Amagi-Player · Политика конфиденциальности v2.0 · 2026-10-28""",
    },
]


# ============================================================================
#  5. LOADER — выбор языка + публичный API
# ============================================================================

import os
from typing import Any

SUPPORTED_LANGS = ("en", "ru")
DEFAULT_LANG = "en"


def _resolve_lang(lang: str | None) -> str:
    """Приоритет: явный lang → env AMAGI_LEGAL_LANG → DEFAULT_LANG."""
    if lang and lang.lower() in SUPPORTED_LANGS:
        return lang.lower()
    env_lang = os.environ.get("AMAGI_LEGAL_LANG", "").strip().lower()
    if env_lang in SUPPORTED_LANGS:
        return env_lang
    return DEFAULT_LANG


def get_disclaimer(lang: str | None = None) -> dict[str, Any]:
    """Возвращает disclaimer для языка: title, version, date, sections."""
    resolved = _resolve_lang(lang)
    if resolved == "ru":
        return {
            "lang": resolved,
            "title": DISCLAIMER_TITLE_RU,
            "version": DISCLAIMER_VERSION_RU,
            "date": DISCLAIMER_DATE_RU,
            "sections": DISCLAIMER_SECTIONS_RU,
        }
    return {
        "lang": resolved,
        "title": DISCLAIMER_TITLE,
        "version": DISCLAIMER_VERSION,
        "date": DISCLAIMER_DATE,
        "sections": DISCLAIMER_SECTIONS,
    }


def get_privacy(lang: str | None = None) -> dict[str, Any]:
    """Возвращает privacy policy для языка: title, version, date, sections."""
    resolved = _resolve_lang(lang)
    if resolved == "ru":
        return {
            "lang": resolved,
            "title": PRIVACY_TITLE_RU,
            "version": PRIVACY_VERSION_RU,
            "date": PRIVACY_DATE_RU,
            "sections": PRIVACY_SECTIONS_RU,
        }
    return {
        "lang": resolved,
        "title": PRIVACY_TITLE,
        "version": PRIVACY_VERSION,
        "date": PRIVACY_DATE,
        "sections": PRIVACY_SECTIONS,
    }


def get_texts(lang: str | None = None) -> dict[str, Any]:
    """Оба документа для выбранного языка."""
    return {
        "lang": _resolve_lang(lang),
        "disclaimer": get_disclaimer(lang),
        "privacy": get_privacy(lang),
    }


# ---------------------------------------------------------------------------
# Обратная совместимость: значения по умолчанию (English)
# ---------------------------------------------------------------------------

DISCLAIMER_TEXT = "\n".join(
    f"{s['title']}\n\n{s['content']}\n" for s in DISCLAIMER_SECTIONS
)
PRIVACY_TEXT = "\n".join(
    f"{s['title']}\n\n{s['content']}\n" for s in PRIVACY_SECTIONS
    )
