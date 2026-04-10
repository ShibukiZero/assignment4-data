# PII Audit Review Preview

## Sample 1

- URI: `http://garveediy.com/index.php?route=product/product&product_id=51`
- Counts: emails=1, phones=3, ips=0, total=4
- Matched emails: contact@ecosummer.com
- Matched phones: 413-822-7850; 413-822-7850; 413-822-7850
- Matched IPs: (none)

### Original Preview

```text
Welcome to my store ! Wrap new offers / gift every single day on Weekends • My Account • Wish List (0) • Compare • Register • Login • track your order • Hotline 413-822-7850 garveediy Store All Categories • Education & Office Supplies • Pet Products • Sports & Outdoors • Toys & Games • Industrial Parts • Book Stationery • Food & Restaurant • Home • Shop banner banner • Marketplace My cart 0 item(s) - $0.00 • Your shopping cart is empty! My Compare • Login • Register Sign in Or Register Forgot Your Password? NEW HERE? Registration is free and easy! • Faster checkout • Save multiple shipping add...
```

### Masked Preview

```text
Welcome to my store ! Wrap new offers / gift every single day on Weekends • My Account • Wish List (0) • Compare • Register • Login • track your order • Hotline |||PHONE_NUMBER||| garveediy Store All Categories • Education & Office Supplies • Pet Products • Sports & Outdoors • Toys & Games • Industrial Parts • Book Stationery • Food & Restaurant • Home • Shop banner banner • Marketplace My cart 0 item(s) - $0.00 • Your shopping cart is empty! My Compare • Login • Register Sign in Or Register Forgot Your Password? NEW HERE? Registration is free and easy! • Faster checkout • Save multiple shippi...
```

## Sample 2

- URI: `http://www.qboru.com/kyguanwangmanbetx/html/zhongyaotiqunongsuoxitong/716.html`
- Counts: emails=0, phones=2, ips=0, total=2
- Matched emails: (none)
- Matched phones: 13868868888; 13868868888
- Matched IPs: (none)

### Original Preview

```text
中文 | English • 网站首页 • MILE.COM米乐体育(中国大陆)科技公司 公司简介 公司风采 公司资质 我们的研发 我们的质量 我们的服务 实验室 抛光工艺 产品检测 焊接技术 CNC加工 • 新闻中心 新闻动态 行业动态 视频中心 • 产品中心 胶体磨系列 搅拌乳化系列 磁力搅拌器系列 卫生输送泵系列 洁净容器罐槽系 过滤器系列 生物发酵罐系列 提取浓缩系统 • 工程案例 生物工程 制药工业 乳品工业 食品工业 酿酒工业 啤酒饮料工业 调味品工业 化妆品工业 化工工业 • 联系我们 提取浓缩系统 PRODUCT CENTER 产品系列 • 胶体磨系列 - JM-L立式胶体磨 - JM-F分体式胶体 - JM-W卧式胶体磨 • 搅拌乳化系列 - WRL高剪切乳化 - SRH均质乳化泵 - FSF高速分散机 - 移动式升降架 - 料液/水粉混合 - 推进式搅拌器 • 磁力搅拌器系 - QLK磁力搅拌器 - QMT磁力搅拌器 - QLK磁悬浮磁力 - 磁力搅拌器 - SDN磁力搅拌器 • 卫生输送泵系 - 卫生泵/离心泵 - 卫生自吸泵 - 卫生转子泵 - 卫生螺杆泵 - 卫生正弦泵 - 卫生隔膜泵 • 洁净容器罐槽 - 储存罐 - 配液罐 - 夹层锅 - 制冷罐 - 冷热罐 - 单层搅拌罐 - 磁力搅拌罐 - 机械搅拌罐 - 反应搅拌罐 - 剪切乳化罐 - 粉体周转料...
```

### Masked Preview

```text
中文 | English • 网站首页 • MILE.COM米乐体育(中国大陆)科技公司 公司简介 公司风采 公司资质 我们的研发 我们的质量 我们的服务 实验室 抛光工艺 产品检测 焊接技术 CNC加工 • 新闻中心 新闻动态 行业动态 视频中心 • 产品中心 胶体磨系列 搅拌乳化系列 磁力搅拌器系列 卫生输送泵系列 洁净容器罐槽系 过滤器系列 生物发酵罐系列 提取浓缩系统 • 工程案例 生物工程 制药工业 乳品工业 食品工业 酿酒工业 啤酒饮料工业 调味品工业 化妆品工业 化工工业 • 联系我们 提取浓缩系统 PRODUCT CENTER 产品系列 • 胶体磨系列 - JM-L立式胶体磨 - JM-F分体式胶体 - JM-W卧式胶体磨 • 搅拌乳化系列 - WRL高剪切乳化 - SRH均质乳化泵 - FSF高速分散机 - 移动式升降架 - 料液/水粉混合 - 推进式搅拌器 • 磁力搅拌器系 - QLK磁力搅拌器 - QMT磁力搅拌器 - QLK磁悬浮磁力 - 磁力搅拌器 - SDN磁力搅拌器 • 卫生输送泵系 - 卫生泵/离心泵 - 卫生自吸泵 - 卫生转子泵 - 卫生螺杆泵 - 卫生正弦泵 - 卫生隔膜泵 • 洁净容器罐槽 - 储存罐 - 配液罐 - 夹层锅 - 制冷罐 - 冷热罐 - 单层搅拌罐 - 磁力搅拌罐 - 机械搅拌罐 - 反应搅拌罐 - 剪切乳化罐 - 粉体周转料...
```

## Sample 3

- URI: `https://carlisleevents.azurewebsites.net/media/press-releases/22?amp;amp;amp;medium=%27nvOpzp%3B+AND+1%3D1+OR+(%3C%27`
- Counts: emails=0, phones=8, ips=0, total=8
- Matched emails: (none)
- Matched phones: 717-960-6400; 717-243-7855; 717-960-6400; 717-243-7855; 717-960-6400; 717-243-7855; (800) 216-1876; (717) 243-7855
- Matched IPs: (none)

### Original Preview

```text
Skip to main content This website uses cookies to ensure you get the best experience on our website. To learn more, review our privacy and cookie policies. Accept Logo • Schedule & Info • Schedule • Directions • Parking • Camping & Trailers • Advance Arrival Planner • Carlisle Events Rules • On-Grounds Transportation • Where to Eat • Branded Merchandise • Kids at Carlisle • Youth Development • In Memoriam • Frequently Asked Questions • About • Founders • Team • Carlisle Fairgrounds • Affiliations • About Us • Employment • Part-Time Jobs • Full-Time Jobs • Glossary • Contact Us • Registration •...
```

### Masked Preview

```text
Skip to main content This website uses cookies to ensure you get the best experience on our website. To learn more, review our privacy and cookie policies. Accept Logo • Schedule & Info • Schedule • Directions • Parking • Camping & Trailers • Advance Arrival Planner • Carlisle Events Rules • On-Grounds Transportation • Where to Eat • Branded Merchandise • Kids at Carlisle • Youth Development • In Memoriam • Frequently Asked Questions • About • Founders • Team • Carlisle Fairgrounds • Affiliations • About Us • Employment • Part-Time Jobs • Full-Time Jobs • Glossary • Contact Us • Registration •...
```

## Sample 4

- URI: `https://energy-thaichamber.org/diesel-50-satang-per-liter/`
- Counts: emails=1, phones=0, ips=0, total=1
- Matched emails: admin@energy-thaichamber.org
- Matched phones: (none)
- Matched IPs: (none)

### Original Preview

```text
Skip to content คณะกรรมการพลังงานหอการค้าไทย • หน้าแรก • เกี่ยวกับเรา • เกี่ยวกับเรา • คณะกรรมการ • ข่าวสารพลังงาน • แพลตฟอร์มซื้อขายคาร์บอนเครดิต • ข้อมูลและความรู้ • ETC E-Learning • ประเด็นสำคัญและความรู้ • วารสาร Green Energy Review • ข้อมูลและเอกสารต่างๆ • ติดต่อเรา ติดต่อเรา Blog คณะกรรมการพลังงานหอการค้าไทย > News & Update > ขยับขึ้นดีเซลอีก 50 สตางค์ต่อลิตรหลังกองทุนน้ำมันวิกฤติติดลบทะลุ 1.1 แสนล้านบาท News & Update ขยับขึ้นดีเซลอีก 50 สตางค์ต่อลิตรหลังกองทุนน้ำมันวิกฤติติดลบทะลุ 1.1 แสนล้านบาท May 20, 2024 Energy Thai Chamber วิกฤติกองทุนน้ำมันติดลบเพิ่มเป็น 1.1 แสนล้าน กบน. สั่งลดการ...
```

### Masked Preview

```text
Skip to content คณะกรรมการพลังงานหอการค้าไทย • หน้าแรก • เกี่ยวกับเรา • เกี่ยวกับเรา • คณะกรรมการ • ข่าวสารพลังงาน • แพลตฟอร์มซื้อขายคาร์บอนเครดิต • ข้อมูลและความรู้ • ETC E-Learning • ประเด็นสำคัญและความรู้ • วารสาร Green Energy Review • ข้อมูลและเอกสารต่างๆ • ติดต่อเรา ติดต่อเรา Blog คณะกรรมการพลังงานหอการค้าไทย > News & Update > ขยับขึ้นดีเซลอีก 50 สตางค์ต่อลิตรหลังกองทุนน้ำมันวิกฤติติดลบทะลุ 1.1 แสนล้านบาท News & Update ขยับขึ้นดีเซลอีก 50 สตางค์ต่อลิตรหลังกองทุนน้ำมันวิกฤติติดลบทะลุ 1.1 แสนล้านบาท May 20, 2024 Energy Thai Chamber วิกฤติกองทุนน้ำมันติดลบเพิ่มเป็น 1.1 แสนล้าน กบน. สั่งลดการ...
```

## Sample 5

- URI: `https://gtaprestigeproperties.com/north-york/bermondsey/`
- Counts: emails=2, phones=2, ips=0, total=4
- Matched emails: homelifemichael@gmail.com; homelifemichael@gmail.com
- Matched phones: 416-918-0657; 416-918-0657
- Matched IPs: (none)

### Original Preview

```text
gtaprestigeproperties.com • Buy • NEW LISTING – 2346 Emerson Drive • New listings • Houses • Toronto Houses • Condos • Townhouses • Recently Sold • Commercial • Rent • Toronto Home Rentals • Condos Rentals • Houses for Rent • New rentals • Sell • Free Home Estimation • Recently Sold Homes Near Me • Blog • Contact • My Account • homelifemichael@gmail.com • 416-918-0657 gtaprestigeproperties.com • Buy • NEW LISTING – 2346 Emerson Drive • New listings • Houses • Toronto Houses • Condos • Townhouses • Recently Sold • Commercial • Rent • Toronto Home Rentals • Condos Rentals • Houses for Rent • New...
```

### Masked Preview

```text
gtaprestigeproperties.com • Buy • NEW LISTING – 2346 Emerson Drive • New listings • Houses • Toronto Houses • Condos • Townhouses • Recently Sold • Commercial • Rent • Toronto Home Rentals • Condos Rentals • Houses for Rent • New rentals • Sell • Free Home Estimation • Recently Sold Homes Near Me • Blog • Contact • My Account • |||EMAIL_ADDRESS||| • |||PHONE_NUMBER||| gtaprestigeproperties.com • Buy • NEW LISTING – 2346 Emerson Drive • New listings • Houses • Toronto Houses • Condos • Townhouses • Recently Sold • Commercial • Rent • Toronto Home Rentals • Condos Rentals • Houses for Rent • New...
```

## Sample 6

- URI: `https://iaindale.blogspot.com/2009/12/one-rule-for-christians.html?showComment=1261309113343`
- Counts: emails=1, phones=0, ips=0, total=1
- Matched emails: nigel.ashton@n-somerset.gov.uk
- Matched phones: (none)
- Matched IPs: (none)

### Original Preview

```text
Iain Dale's Diary political commentator * author * publisher * bookseller * radio presenter * blogger * Conservative candidate * former lobbyist * Jack Russell owner * West Ham United fanatic * Email iain AT iaindale DOT com Sunday, December 20, 2009 One Rule for Christians... The Mail on Sunday's lead story this morning concerns a teacher who has been sacked for offering comfort to the parent of a sick child by offering to pray for the her. The teacher specialised in teaching children too ill to attend school. The parent made a complaint and the teacher was sacked by her managers. Let's, for ...
```

### Masked Preview

```text
Iain Dale's Diary political commentator * author * publisher * bookseller * radio presenter * blogger * Conservative candidate * former lobbyist * Jack Russell owner * West Ham United fanatic * Email iain AT iaindale DOT com Sunday, December 20, 2009 One Rule for Christians... The Mail on Sunday's lead story this morning concerns a teacher who has been sacked for offering comfort to the parent of a sick child by offering to pray for the her. The teacher specialised in teaching children too ill to attend school. The parent made a complaint and the teacher was sacked by her managers. Let's, for ...
```

## Sample 7

- URI: `https://learneo.fr/formation-it-et-management/pre-inscription/?formation=F-ISO-27001LI`
- Counts: emails=1, phones=0, ips=0, total=1
- Matched emails: info@learneo.fr
- Matched phones: (none)
- Matched IPs: (none)

### Original Preview

```text
Aller au contenu Calendrier • info@learneo.fr Learneo : formations et services IT • FORMATIONS Picto violet ordinateur sur pied INFRASTRUCTURE RÉSEAUX DATACENTER • ETAT DE L'ART • CISCO SYSTEMS • HUAWEI • ARISTA • UCOPIA (Weblib) Picto Cloud entrée sortie CLOUD & VIRTUALISATION, DATA / IA • MICROSOFT • AMAZON WEB SERVICES (AWS) • VEEAM • VMWARE by BROADCOM Picto cadenas lock CYBERSÉCURITÉ • CISCO • EC COUNCIL • FORTINET • ISACA • NORMES ISO (PECB) Picto process management MANAGEMENT IT • GESTION DE PROJETS • IT SERVICE MANAGEMENT Toutes nos formations • CERTIFICATION • DE QUOI PARLE-T-ON? • CE...
```

### Masked Preview

```text
Aller au contenu Calendrier • |||EMAIL_ADDRESS||| Learneo : formations et services IT • FORMATIONS Picto violet ordinateur sur pied INFRASTRUCTURE RÉSEAUX DATACENTER • ETAT DE L'ART • CISCO SYSTEMS • HUAWEI • ARISTA • UCOPIA (Weblib) Picto Cloud entrée sortie CLOUD & VIRTUALISATION, DATA / IA • MICROSOFT • AMAZON WEB SERVICES (AWS) • VEEAM • VMWARE by BROADCOM Picto cadenas lock CYBERSÉCURITÉ • CISCO • EC COUNCIL • FORTINET • ISACA • NORMES ISO (PECB) Picto process management MANAGEMENT IT • GESTION DE PROJETS • IT SERVICE MANAGEMENT Toutes nos formations • CERTIFICATION • DE QUOI PARLE-T-ON? ...
```

## Sample 8

- URI: `https://mentormpact.com/tag/how-to-fund-mba/`
- Counts: emails=1, phones=1, ips=0, total=2
- Matched emails: help@mentormpact.com
- Matched phones: 9811175204
- Matched IPs: (none)

### Original Preview

```text
fbpx Skip to content Mentor Mpact Mentor Mpact • About Us • Who are we? • Our Advantage • The Mentor Network • Our Services • MBA Admissions • Comprehensive Package • HeadStart Program • Interview Package • Master’s Admissions • Admission Resources • MentorMpact Profile Evaluation • MBA Deadlines • Success Stories • Admits & Track Record • MBA Testimonials • Master’s Testimonials • Blog • Contact Us Mentor Mpact • About Us • Who are we? • Our Advantage • The Mentor Network • Our Services • MBA Admissions • Comprehensive Package • HeadStart Program • Interview Package • Master’s Admissions • Ad...
```

### Masked Preview

```text
fbpx Skip to content Mentor Mpact Mentor Mpact • About Us • Who are we? • Our Advantage • The Mentor Network • Our Services • MBA Admissions • Comprehensive Package • HeadStart Program • Interview Package • Master’s Admissions • Admission Resources • MentorMpact Profile Evaluation • MBA Deadlines • Success Stories • Admits & Track Record • MBA Testimonials • Master’s Testimonials • Blog • Contact Us Mentor Mpact • About Us • Who are we? • Our Advantage • The Mentor Network • Our Services • MBA Admissions • Comprehensive Package • HeadStart Program • Interview Package • Master’s Admissions • Ad...
```

## Sample 9

- URI: `https://seolistlinks.com/story20597310/oregon-city-vape-shops-your-local-connection`
- Counts: emails=0, phones=1, ips=0, total=1
- Matched emails: (none)
- Matched phones: 214-644-0203
- Matched IPs: (none)

### Original Preview

```text
seolistlinks forum • Home • New • Submit • Groups • Register • Login • Home • Home 1 Oregon City Vape Shops: Your Local Connection heidirekh857436 22 days ago News Discuss Looking for the Best vape shops in Oregon City? Look no further! Our city has a Bomb selection of vape stores, each offering Incredible deals on all your favorite vapes and accessories. Whether you're a Cloud Chaser, https://maedmzt393620.slypage.com/34433666/oregon-city-vape-shops-your-local-hangout • Comments • Who Upvoted Comments No HTML HTML is disabled Report Page Who Upvoted this Story Search Published News • 1 Not kn...
```

### Masked Preview

```text
seolistlinks forum • Home • New • Submit • Groups • Register • Login • Home • Home 1 Oregon City Vape Shops: Your Local Connection heidirekh857436 22 days ago News Discuss Looking for the Best vape shops in Oregon City? Look no further! Our city has a Bomb selection of vape stores, each offering Incredible deals on all your favorite vapes and accessories. Whether you're a Cloud Chaser, https://maedmzt393620.slypage.com/34433666/oregon-city-vape-shops-your-local-hangout • Comments • Who Upvoted Comments No HTML HTML is disabled Report Page Who Upvoted this Story Search Published News • 1 Not kn...
```

## Sample 10

- URI: `https://www.fargotime.com/products/emporio-armani-womens-dress-watch-ar11092`
- Counts: emails=1, phones=1, ips=2, total=4
- Matched emails: support@fargotime.com
- Matched phones: 1-866-327-4626
- Matched IPs: 120.210.17.116; 120.210.17.116

### Original Preview

```text
Skip to content en CAD THOUSANDS OF SATISFIED CUSTOMERS ⭐️⭐️⭐️⭐️⭐️ SUPPORT CANADIAN BUSINESSES 🇨🇦 FARGO TIME - SINCE 1997 • Customer Reviews • Diamonds • Shop All • Men's Watches • Ladies Watches • Under $300 • $300 to $500 • $500 to $1000 • $1000 & Above • Track Your Order • Hamilton • Roamer • Rado • Gucci • Seiko • Citizen • Sternglas • Jacques Du Manoir • JDM Military • Michael Kors • Swarovski • Diesel • Emporio Armani • Maserati • Hugo Boss • Guess • Tommy Hilfiger • Glam Rock • Kenneth Cole Log in Log in en CAD FargoTime.com • Customer Reviews • Diamonds • Shop All • Men's Watches • L...
```

### Masked Preview

```text
Skip to content en CAD THOUSANDS OF SATISFIED CUSTOMERS ⭐️⭐️⭐️⭐️⭐️ SUPPORT CANADIAN BUSINESSES 🇨🇦 FARGO TIME - SINCE 1997 • Customer Reviews • Diamonds • Shop All • Men's Watches • Ladies Watches • Under $300 • $300 to $500 • $500 to $1000 • $1000 & Above • Track Your Order • Hamilton • Roamer • Rado • Gucci • Seiko • Citizen • Sternglas • Jacques Du Manoir • JDM Military • Michael Kors • Swarovski • Diesel • Emporio Armani • Maserati • Hugo Boss • Guess • Tommy Hilfiger • Glam Rock • Kenneth Cole Log in Log in en CAD FargoTime.com • Customer Reviews • Diamonds • Shop All • Men's Watches • L...
```

## Sample 11

- URI: `https://www.hmsolicitorsltd.com/category/child-law/our-child-law-services/child-maintenance/`
- Counts: emails=2, phones=0, ips=0, total=2
- Matched emails: info@website.com; info@hmsolicitorsltd.com
- Matched phones: (none)
- Matched IPs: (none)

### Original Preview

```text
Skip to content Skip to footer • About • Family Law • Divorce • Our Divorce Services • Divorce lawyers & divorce solicitors • Divorce Online • Fixed Fee Divorce • Civil Partnership Dissolution • International Divorce • High Net Worth Divorce • International Divorce • Islamic Sharia Law Divorce • Jewish Divorce • Religious Law • Divorce Coaching • Avoiding Court • Out of Court Divorce • Family mediators for divorce • Collaborative Divorce • Hybrid Mediation • Arbitration for Divorce • Divorce Advice • Adultery and Divorce • Are you thinking about a divorce or separation? • Home Rights Notices i...
```

### Masked Preview

```text
Skip to content Skip to footer • About • Family Law • Divorce • Our Divorce Services • Divorce lawyers & divorce solicitors • Divorce Online • Fixed Fee Divorce • Civil Partnership Dissolution • International Divorce • High Net Worth Divorce • International Divorce • Islamic Sharia Law Divorce • Jewish Divorce • Religious Law • Divorce Coaching • Avoiding Court • Out of Court Divorce • Family mediators for divorce • Collaborative Divorce • Hybrid Mediation • Arbitration for Divorce • Divorce Advice • Adultery and Divorce • Are you thinking about a divorce or separation? • Home Rights Notices i...
```

## Sample 12

- URI: `https://www.hollandgold.nl/en/buy-gold/buy-gold-coins.html?selectie=831`
- Counts: emails=2, phones=0, ips=0, total=2
- Matched emails: klantenservice@hollandgold.nl; klantenservice@hollandgold.nl
- Matched phones: (none)
- Matched IPs: (none)

### Original Preview

```text
9.5 7.175 Reviews • Frequently Asked Questions • About us • Contact • Open an account English en Nederlands NL English EN Holland Gold • Buy gold • Gold Coins 1/10 Troy Ounce1/10 Troy Ounce 1/4 Troy Ounce1/4 Troy Ounce 1/2 Troy Ounce1/2 Troy Ounce 1 Troy Ounce1 Troy Ounce 2 Troy Ounce2 Troy Ounce More gold coins Gold bars 10 grams10 grams 1 Troy Ounce1 Troy Ounce 50 grams50 grams 100 grams100 grams 1 kilogram1 kilogram More gold bars Products C. Hafner Umicore Valcambi SA Maple Leaf Krugerrand More products Best Sellers Buy gold by the gram in insured storage Buy gold by the gram in insured st...
```

### Masked Preview

```text
9.5 7.175 Reviews • Frequently Asked Questions • About us • Contact • Open an account English en Nederlands NL English EN Holland Gold • Buy gold • Gold Coins 1/10 Troy Ounce1/10 Troy Ounce 1/4 Troy Ounce1/4 Troy Ounce 1/2 Troy Ounce1/2 Troy Ounce 1 Troy Ounce1 Troy Ounce 2 Troy Ounce2 Troy Ounce More gold coins Gold bars 10 grams10 grams 1 Troy Ounce1 Troy Ounce 50 grams50 grams 100 grams100 grams 1 kilogram1 kilogram More gold bars Products C. Hafner Umicore Valcambi SA Maple Leaf Krugerrand More products Best Sellers Buy gold by the gram in insured storage Buy gold by the gram in insured st...
```

## Sample 13

- URI: `https://www.librinlinea.it/search/public/appl/list.php?facet=1&classPath=%2Beditore_31400`
- Counts: emails=1, phones=0, ips=0, total=1
- Matched emails: culturaturismosport@regione.piemonte.it
- Matched phones: (none)
- Matched IPs: (none)

### Original Preview

```text
Salta al contenuto principale - Vai al menu contestuale • Ricerca • Biblioteche • Altri cataloghi • Cos'è Librinlinea Il numero minimo di caratteri da inserire è 1 Modifica » Stai cercando in... Tutte le biblioteche Filtri di ricerca Elimina I tuoi preferiti • Non ci sono schede preferite Elimina Ricerche recenti • Non ci sono ricerche recenti Elimina Schede viste di recente • Non ci sono schede viste di recente Dichiarazione di accessibilità - Accessibilità meccanismo di feedback - Servizio a cura della Direzione Regionale A20000 - Promozione della Cultura, del Turismo e dello Sport - Via Ber...
```

### Masked Preview

```text
Salta al contenuto principale - Vai al menu contestuale • Ricerca • Biblioteche • Altri cataloghi • Cos'è Librinlinea Il numero minimo di caratteri da inserire è 1 Modifica » Stai cercando in... Tutte le biblioteche Filtri di ricerca Elimina I tuoi preferiti • Non ci sono schede preferite Elimina Ricerche recenti • Non ci sono ricerche recenti Elimina Schede viste di recente • Non ci sono schede viste di recente Dichiarazione di accessibilità - Accessibilità meccanismo di feedback - Servizio a cura della Direzione Regionale A20000 - Promozione della Cultura, del Turismo e dello Sport - Via Ber...
```

## Sample 14

- URI: `https://www.nutrizionistacecconi.it/la-spesa-di-settembre/`
- Counts: emails=0, phones=2, ips=0, total=2
- Matched emails: (none)
- Matched phones: 340 3317442; 0247020037
- Matched IPs: (none)

### Original Preview

```text
Salta al contenuto • Home • Bio • Blog • Ricette • Salate • Dolci • Eventi • E-book • Contatti Menu • Home • Bio • Blog • Ricette • Salate • Dolci • Eventi • E-book • Contatti Instagram Facebook-f Linkedin Tiktok Prenota una visita la spesa di settembre • Articolo pubblicato:23 Agosto 2022 • Categoria dell'articolo:Consigli alimentari La spesa di settembre L’estate sta finendo… cantava una vecchia canzone, e settembre porta con sé proprio la fine dell’estate. É il mese in cui a tavola troviamo alcuni prodotti estivi che pian piano lasciano spazio a frutta e verdura più autunnali. Io personalme...
```

### Masked Preview

```text
Salta al contenuto • Home • Bio • Blog • Ricette • Salate • Dolci • Eventi • E-book • Contatti Menu • Home • Bio • Blog • Ricette • Salate • Dolci • Eventi • E-book • Contatti Instagram Facebook-f Linkedin Tiktok Prenota una visita la spesa di settembre • Articolo pubblicato:23 Agosto 2022 • Categoria dell'articolo:Consigli alimentari La spesa di settembre L’estate sta finendo… cantava una vecchia canzone, e settembre porta con sé proprio la fine dell’estate. É il mese in cui a tavola troviamo alcuni prodotti estivi che pian piano lasciano spazio a frutta e verdura più autunnali. Io personalme...
```

## Sample 15

- URI: `https://www.pivni-nebe.cz/praotec-svetly-lezak-12/`
- Counts: emails=1, phones=0, ips=0, total=1
- Matched emails: pivni.nebe@gmail.com
- Matched phones: (none)
- Matched IPs: (none)

### Original Preview

```text
Přihlášení k vašemu účtu Nemůžete vyplnit toto pole Nová registraceZapomenuté heslo • Obchodní podmínky • Podmínky ochrany osobních údajů • Kontakty Více PřihlášeníRegistrace pivni-nebe.cz Hledat Nákupní košík Prázdný košík • Nápoje • Pivo • Sudové pivo skladem, • Sudové pivo - na objednávku, • Minipivovary - lahvové pivo - plech, • Nealkoholické pivo, • Belgická a Německá piva, • DÁRKOVÉ PIVO, • Dánské pivo • Víno • Lahoffer, • Vinařství Martin Novák, • PROSECCO, • BOHEMIA SEKT • Limo • Lahvové, • Sudové, • TEA VOLE • GIN • ENDORPHINE • Delikatesy • Utopenci • Sušené maso • Farmářské brambůrk...
```

### Masked Preview

```text
Přihlášení k vašemu účtu Nemůžete vyplnit toto pole Nová registraceZapomenuté heslo • Obchodní podmínky • Podmínky ochrany osobních údajů • Kontakty Více PřihlášeníRegistrace pivni-nebe.cz Hledat Nákupní košík Prázdný košík • Nápoje • Pivo • Sudové pivo skladem, • Sudové pivo - na objednávku, • Minipivovary - lahvové pivo - plech, • Nealkoholické pivo, • Belgická a Německá piva, • DÁRKOVÉ PIVO, • Dánské pivo • Víno • Lahoffer, • Vinařství Martin Novák, • PROSECCO, • BOHEMIA SEKT • Limo • Lahvové, • Sudové, • TEA VOLE • GIN • ENDORPHINE • Delikatesy • Utopenci • Sušené maso • Farmářské brambůrk...
```

## Sample 16

- URI: `https://www.soinspersonnels.com/nouvelles/379`
- Counts: emails=0, phones=3, ips=0, total=3
- Matched emails: (none)
- Matched phones: 514 844-3020; 1 866 682 6040; 514 844-1930
- Matched IPs: (none)

### Original Preview

```text
logo logo Formation, reconnaissance des compÃ©tences, gestion RH - Une force engagÃ©e Ã votre dÃ©veloppement! RÃ©pertoire recherche facebook youtube Nous joindre • RCMO Nos Formations • RCMO La Reconnaissance des CompÃ©tences RCMO • RCMO Le Programme d'Apprentissage en Millieu de Travail PAMT • RCMO Outils RH • RCMO RÃ©ussites de nos professionnels • RCMO Nouvelles Infolettre Inscrivez-vous! Blogue • Ã€ Propos • Les comitÃ©s sectoriels • Les secteurs des services des soins personnels • Notre mission • Notre conseil dâ€™administration et notre permanence • Nos publications gÃ©nÃ©rales • Nos inf...
```

### Masked Preview

```text
logo logo Formation, reconnaissance des compÃ©tences, gestion RH - Une force engagÃ©e Ã votre dÃ©veloppement! RÃ©pertoire recherche facebook youtube Nous joindre • RCMO Nos Formations • RCMO La Reconnaissance des CompÃ©tences RCMO • RCMO Le Programme d'Apprentissage en Millieu de Travail PAMT • RCMO Outils RH • RCMO RÃ©ussites de nos professionnels • RCMO Nouvelles Infolettre Inscrivez-vous! Blogue • Ã€ Propos • Les comitÃ©s sectoriels • Les secteurs des services des soins personnels • Notre mission • Notre conseil dâ€™administration et notre permanence • Nos publications gÃ©nÃ©rales • Nos inf...
```

## Sample 17

- URI: `https://www.st-ob.ru/upload/iblock/a4d/a4d58e582e3743eb6a3e9a36cd69166b.pdf`
- Counts: emails=6, phones=0, ips=0, total=6
- Matched emails: E@NH.oB; ea%@x.dvz; LO@B.EaA; P@pi.ZP; i@vjW.quM; J@G.jk
- Matched phones: (none)
- Matched IPs: (none)

### Original Preview

```text
%PDF-1.6 % 225 0 obj <> endobj 244 0 obj <>/Filter/FlateDecode/ID[<7663406EC258D54E8F6EB18003CF6476>]/Index[225 27]/Info 224 0 R/Length 92/Prev 20804017/Root 226 0 R/Size 252/Type/XRef/W[1 2 1]>>stream hbbd``b`N N@i' $xOTH؃X@pqč?H(v )@B7d<#V?o0 endstream endobj startxref 0 %%EOF 251 0 obj <>stream hb```"KVA~q10pTXmg|y (&!=_&q?m,XyRĥ.,5GQɧ˕䤘W3~=rJnxX `^KS٨%lMRFaRSN4U+d\3ʕЫ2:; hdVLG*(3҂@ Ae1<{> P_5ʍKaF1AAu'oJ*x*Ѷ$fy endstream endobj 226 0 obj <> endobj 227 0 obj <>/ExtGState<>/Font<>/ProcSet[/PDF/Text/ImageC]/XObject<>>>/Rotate 0/Tr...
```

### Masked Preview

```text
%PDF-1.6 % 225 0 obj <> endobj 244 0 obj <>/Filter/FlateDecode/ID[<7663406EC258D54E8F6EB18003CF6476>]/Index[225 27]/Info 224 0 R/Length 92/Prev 20804017/Root 226 0 R/Size 252/Type/XRef/W[1 2 1]>>stream hbbd``b`N N@i' $xOTH؃X@pqč?H(v )@B7d<#V?o0 endstream endobj startxref 0 %%EOF 251 0 obj <>stream hb```"KVA~q10pTXmg|y (&!=_&q?m,XyRĥ.,5GQɧ˕䤘W3~=rJnxX `^KS٨%lMRFaRSN4U+d\3ʕЫ2:; hdVLG*(3҂@ Ae1<{> P_5ʍKaF1AAu'oJ*x*Ѷ$fy endstream endobj 226 0 obj <> endobj 227 0 obj <>/ExtGState<>/Font<>/ProcSet[/PDF/Text/ImageC]/XObject<>>>/Rotate 0/Tr...
```

## Sample 18

- URI: `https://www.telebrand.com.pk/product-tag/iron-gym-bar/`
- Counts: emails=1, phones=2, ips=0, total=3
- Matched emails: order@telebrand.com.pk
- Matched phones: 311 1222089; 321 4115583
- Matched IPs: (none)

### Original Preview

```text
a All ×    0 No products in the cart • Home • Blogs • Contact us • Shop • My Account ~ 100% Secure delivery | Need help? Call Us: 0321 4115583 × M • Home • Blogs • Contact us • Shop • My Account Log In • Follow • Follow • Follow • Follow • Follow • Follow Home / Products tagged “iron gym bar” iron gym bar Showing the single result • Iron Gym Bar Iron Gym Bar ₨ 3,000 Add to cart Search Product by its Name Recent Posts • Casual Shirts for Men and Women • Pocket Chair • Trusty Cane • Car Electric Shaver • Massage Mat Recent Comments • usman on Caboki hair fiber • Umama on Derma Roller • zahid ...
```

### Masked Preview

```text
a All ×    0 No products in the cart • Home • Blogs • Contact us • Shop • My Account ~ 100% Secure delivery | Need help? Call Us: 0321 4115583 × M • Home • Blogs • Contact us • Shop • My Account Log In • Follow • Follow • Follow • Follow • Follow • Follow Home / Products tagged “iron gym bar” iron gym bar Showing the single result • Iron Gym Bar Iron Gym Bar ₨ 3,000 Add to cart Search Product by its Name Recent Posts • Casual Shirts for Men and Women • Pocket Chair • Trusty Cane • Car Electric Shaver • Massage Mat Recent Comments • usman on Caboki hair fiber • Umama on Derma Roller • zahid ...
```

## Sample 19

- URI: `https://www.thinbluelinecareers.com/careers-1/ba126b7a-b7ea-450c-b348-aed8823bc3b3`
- Counts: emails=1, phones=0, ips=0, total=1
- Matched emails: support@thinbluelinecareers.com
- Matched phones: (none)
- Matched IPs: (none)

### Original Preview

```text
top of page • Home • Agencies • Careers • Announcements • Join TBLC • More Use tab to navigate through the menu items. ThinBlueLineCareers.com Innovating Recruiting There’s Nothing Here... We can’t find the page you’re looking for. Check the URL, or head back home. Go Home Back to Top © 2024 by BlueGovTech Contact Us support@thinbluelinecareers.com • LinkedIn bottom of page
```

### Masked Preview

```text
top of page • Home • Agencies • Careers • Announcements • Join TBLC • More Use tab to navigate through the menu items. ThinBlueLineCareers.com Innovating Recruiting There’s Nothing Here... We can’t find the page you’re looking for. Check the URL, or head back home. Go Home Back to Top © 2024 by BlueGovTech Contact Us |||EMAIL_ADDRESS||| • LinkedIn bottom of page
```

## Sample 20

- URI: `https://www2.nchu.edu.tw/news-detail/id/10717`
- Counts: emails=1, phones=0, ips=0, total=1
- Matched emails: yucheliu@mail.nchu.edu.tw
- Matched phones: (none)
- Matched IPs: (none)

### Original Preview

```text
﻿ 【徵才】動物科學系林亮全教授誠徵碩(學)士級研究助理一名 - 國立中興大學(National Chung Hsing University) 跳到主要內容區塊 國立中興大學 ::: • 網站導覽 • NUST臺灣國立大學系統 ASK NCHU • 訪客選單鈕 • 搜尋選單鈕 • 中文版 • English • 認識興大 • 興大簡介 • 簡史 • 歷任校長 • 影音文宣簡介 • 興大簡訊 • 學校發展重點 • 校區及校產 • 學生生活 • 委員會 • 名譽博士 • 南投分部 • 南投分部網站 • 簡介 • 南投分部整體規劃藍圖 • 交通資訊 • 興湖紀事 • 學校定位.教育目標.基本素養。校徽。LOGO • 校徽設計理念 • 校徽識別系統-基本設計 • 校徽識別系統-應用設計 • Logo設計理念 • 禮品主視覺設計 • 學校定位與教育目標 • 學生基本素養 • 校園欣賞 • 資訊公開 • 中程校務發展計畫 • 校務財務資訊公開 • 高教深耕計畫 • 統計年報 • 永續報告書 • 大學系統績效報告書 • 重大工程執行情形 • 興大作業輯要 • 興大法規輯要 • 教學單位簡稱 • 地圖 • 如何到興大 • 校本部配置圖 • 南投校區平面圖 • 興大校本部 - Google 街景 • 校園AED配置圖 • 教學 • 文學院 • 文學院網站 • 文學院簡介 • 單位公告 • 中國文學...
```

### Masked Preview

```text
﻿ 【徵才】動物科學系林亮全教授誠徵碩(學)士級研究助理一名 - 國立中興大學(National Chung Hsing University) 跳到主要內容區塊 國立中興大學 ::: • 網站導覽 • NUST臺灣國立大學系統 ASK NCHU • 訪客選單鈕 • 搜尋選單鈕 • 中文版 • English • 認識興大 • 興大簡介 • 簡史 • 歷任校長 • 影音文宣簡介 • 興大簡訊 • 學校發展重點 • 校區及校產 • 學生生活 • 委員會 • 名譽博士 • 南投分部 • 南投分部網站 • 簡介 • 南投分部整體規劃藍圖 • 交通資訊 • 興湖紀事 • 學校定位.教育目標.基本素養。校徽。LOGO • 校徽設計理念 • 校徽識別系統-基本設計 • 校徽識別系統-應用設計 • Logo設計理念 • 禮品主視覺設計 • 學校定位與教育目標 • 學生基本素養 • 校園欣賞 • 資訊公開 • 中程校務發展計畫 • 校務財務資訊公開 • 高教深耕計畫 • 統計年報 • 永續報告書 • 大學系統績效報告書 • 重大工程執行情形 • 興大作業輯要 • 興大法規輯要 • 教學單位簡稱 • 地圖 • 如何到興大 • 校本部配置圖 • 南投校區平面圖 • 興大校本部 - Google 街景 • 校園AED配置圖 • 教學 • 文學院 • 文學院網站 • 文學院簡介 • 單位公告 • 中國文學...
```

