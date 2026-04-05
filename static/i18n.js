/**
 * i18n.js — Traductions multilingues du site BININGA
 * Langues : fr · en · es · zh · ru
 */

const I18N = {

  fr: {
    // ── Navigation ──────────────────────────────────────────────
    "nav.biography":    "Biographie",
    "nav.parcours":     "Parcours",
    "nav.publication":  "Publication",
    "nav.programme":    "Programme",
    "nav.gallery":      "Galerie",
    "nav.news":         "Actualités",
    "nav.contact":      "Contact",
    "nav.audience":     "Audience",

    // ── Hero ────────────────────────────────────────────────────
    "hero.btn1":        "🤝 Rejoindre la campagne",
    "hero.btn2":        "Notre programme",
    "hero.scroll":      "Découvrir",

    // ── About ───────────────────────────────────────────────────
    "about.tag":        "Qui est-il ?",
    "about.title":      "Un homme forgé par",
    "about.title.em":   "le terrain",
    "about.badge.lbl":  "Sa circonscription",

    // ── Parcours ────────────────────────────────────────────────
    "parcours.tag":     "Son parcours",
    "parcours.title":   "Une carrière bâtie sur",
    "parcours.accent":  "la confiance",

    // ── Programme ───────────────────────────────────────────────
    "prog.tag":         "Son programme",
    "prog.title":       "Un projet pour",
    "prog.accent":      "Ewo et le Congo",

    // ── Engagement form ─────────────────────────────────────────
    "eng.tag":          "Contactez-nous",
    "eng.title":        "Une réclamation ou une",
    "eng.title.accent": "demande",
    "eng.desc":         "Vous avez une réclamation, une préoccupation ou souhaitez prendre contact avec l'équipe du Député ? Soumettez votre demande d'audience et nous vous reviendrons dans les meilleurs délais.",
    "eng.card1.title":  "Demande d'audience",
    "eng.card1.desc":   "Rencontrez le Député pour exposer votre situation",
    "eng.card2.title":  "Réclamation officielle",
    "eng.card2.desc":   "Signalez un problème auprès de votre représentant",
    "eng.card3.title":  "Prise de contact",
    "eng.card3.desc":   "Entrez en relation avec l'équipe du Député d'Ewo",
    "form.aud.title":   "Demande d'audience auprès du Député",
    "form.aud.sub":     "Expliquez l'objet de votre demande, notre équipe vous contactera sous 48h",
    "form.firstname":   "Prénom *",
    "form.firstname.ph":"Votre prénom",
    "form.lastname":    "Nom *",
    "form.lastname.ph": "Votre nom",
    "form.address":     "Adresse *",
    "form.address.ph":  "Votre adresse complète",
    "form.phone":       "Téléphone *",
    "form.email":       "Email",
    "form.object":      "Objet de la demande *",
    "form.obj.aud":     "Demande d'audience",
    "form.obj.recl":    "Réclamation / Signalement",
    "form.obj.q":       "Question au Député",
    "form.obj.other":   "Autre",
    "form.reason":      "Raison de la demande *",
    "form.reason.ph":   "Rédigez ici votre requête. Expliquez l'objet de votre demande, votre situation, et ce que vous attendez du Député…",
    "form.submit.aud":  "📨 Soumettre ma demande",
    "form.recl.badge":  "⚠️ Signalement officiel",
    "form.recl.desc":   "Description du sinistre / problème *",
    "form.recl.desc.ph":"Décrivez précisément le problème, le sinistre ou la situation à signaler au Député…",
    "form.geo.title":   "📍 Localisation du sinistre",
    "form.geo.status":  "Non localisé, cliquez pour géolocaliser",
    "form.geo.btn":     "📍 Géolocaliser ma position",
    "form.photo.lbl":   "📷 Photo du sinistre",
    "form.photo.opt":   "(optionnel, jpg/png, max 3 Mo)",

    // ── CTA ─────────────────────────────────────────────────────
    "cta.title":        "Votez BININGA :\nle choix de l'expérience et du terrain",
    "cta.sub":          "Parce qu'Ewo mérite un homme qui connaît l'État de l'intérieur et le terrain de cœur.",
    "cta.btn1":         "📋 Demande d'audience",
    "cta.btn2":         "✉️ Nous contacter",
    "cta.btn3":         "📋 Lire le programme",

    // ── Contact ─────────────────────────────────────────────────
    "ct.tag":           "Nous écrire",
    "ct.title":         "Prenez",
    "ct.accent":        "contact",
    "ct.sidebar.title": "Quartier Général\nde Campagne",
    "ct.sidebar.desc":  "Notre équipe répond à vos questions, traite vos demandes de rencontre et organise vos échanges avec le candidat Aimé BININGA.",
    "ct.lbl.address":   "Adresse",
    "ct.lbl.phone":     "Téléphone",
    "ct.lbl.email":     "Email",
    "ct.lbl.social":    "Réseaux sociaux",
    "ct.form.title":    "Envoyez un message",
    "ct.form.firstname":"Prénom",
    "ct.form.lastname": "Nom",
    "ct.form.email":    "Email",
    "ct.form.subject":  "Sujet",
    "ct.subj.general":  "Question générale",
    "ct.subj.meeting":  "Demande de rencontre",
    "ct.subj.speech":   "Prise de parole",
    "ct.subj.press":    "Presse / Journaliste",
    "ct.subj.partner":  "Partenariat",
    "ct.form.message":  "Message",
    "ct.form.msg.ph":   "Votre message...",
    "ct.form.send":     "📨 Envoyer le message",

    // ── Newsletter ───────────────────────────────────────────────
    "nl.title":         "Restez informé",
    "nl.desc":          "Recevez les actualités, les initiatives et les avancées du Député directement dans votre boîte mail. Pas de spam, une lettre mensuelle.",
    "nl.btn":           "📩 S'inscrire",
    "nl.legal":         "En vous inscrivant, vous acceptez notre",
    "nl.legal.link":    "politique de confidentialité",
    "nl.ok":            "✅ Inscription confirmée, merci pour votre soutien !",

    // ── Footer ──────────────────────────────────────────────────
    "ft.nav":           "Navigation",
    "ft.engage":        "S'engager",
    "ft.legal":         "Légal",
    "ft.volunteer":     "Devenir bénévole",
    "ft.newsletter":    "Newsletter",
    "ft.press":         "Presse",
    "ft.mentions":      "Mentions légales",
    "ft.privacy":       "Confidentialité",
    "ft.copyright":     "© 2026 Campagne Aimé BININGA · Parti Congolais du Travail · Tous droits réservés",

    // ── Chat ────────────────────────────────────────────────────
    "chat.placeholder": "Posez votre question à DA…",
    "chat.send":        "Envoyer",
    "chat.title":       "Assistant DA",
    "chat.greeting":    "Bonjour ! Je suis DA, l'assistant virtuel du site. Posez-moi vos questions sur Ange Aimé Wilfrid BININGA.",
  },

  en: {
    "nav.biography":    "Biography",
    "nav.parcours":     "Career",
    "nav.publication":  "Publication",
    "nav.programme":    "Programme",
    "nav.gallery":      "Gallery",
    "nav.news":         "News",
    "nav.contact":      "Contact",
    "nav.audience":     "Audience",

    "hero.btn1":        "🤝 Join the campaign",
    "hero.btn2":        "Our programme",
    "hero.scroll":      "Discover",

    "about.tag":        "Who is he?",
    "about.title":      "A man shaped by",
    "about.title.em":   "the field",
    "about.badge.lbl":  "His constituency",

    "parcours.tag":     "His career",
    "parcours.title":   "A career built on",
    "parcours.accent":  "trust",

    "prog.tag":         "His programme",
    "prog.title":       "A project for",
    "prog.accent":      "Ewo and Congo",

    "eng.tag":          "Contact us",
    "eng.title":        "A complaint or a",
    "eng.title.accent": "request",
    "eng.desc":         "Do you have a complaint, concern or wish to contact the Deputy's team? Submit your audience request and we will get back to you as soon as possible.",
    "eng.card1.title":  "Audience request",
    "eng.card1.desc":   "Meet the Deputy to present your situation",
    "eng.card2.title":  "Official complaint",
    "eng.card2.desc":   "Report a problem to your representative",
    "eng.card3.title":  "Get in touch",
    "eng.card3.desc":   "Connect with the team of the Deputy of Ewo",
    "form.aud.title":   "Audience Request to the Deputy",
    "form.aud.sub":     "Explain the purpose of your request, our team will contact you within 48h",
    "form.firstname":   "First name *",
    "form.firstname.ph":"Your first name",
    "form.lastname":    "Last name *",
    "form.lastname.ph": "Your last name",
    "form.address":     "Address *",
    "form.address.ph":  "Your full address",
    "form.phone":       "Phone *",
    "form.email":       "Email",
    "form.object":      "Request subject *",
    "form.obj.aud":     "Audience request",
    "form.obj.recl":    "Complaint / Report",
    "form.obj.q":       "Question to the Deputy",
    "form.obj.other":   "Other",
    "form.reason":      "Reason for request *",
    "form.reason.ph":   "Write your request here. Explain the purpose, your situation, and what you expect from the Deputy…",
    "form.submit.aud":  "📨 Submit my request",
    "form.recl.badge":  "⚠️ Official report",
    "form.recl.desc":   "Description of the issue / problem *",
    "form.recl.desc.ph":"Describe precisely the problem or situation to report to the Deputy…",
    "form.geo.title":   "📍 Incident location",
    "form.geo.status":  "Not located, click to geolocate",
    "form.geo.btn":     "📍 Geolocate my position",
    "form.photo.lbl":   "📷 Photo of the incident",
    "form.photo.opt":   "(optional, jpg/png, max 3 MB)",

    "cta.title":        "Vote BININGA:\nthe choice of experience and fieldwork",
    "cta.sub":          "Because Ewo deserves a man who knows the State from the inside and the field from the heart.",
    "cta.btn1":         "📋 Audience request",
    "cta.btn2":         "✉️ Contact us",
    "cta.btn3":         "📋 Read the programme",

    "ct.tag":           "Write to us",
    "ct.title":         "Get in",
    "ct.accent":        "touch",
    "ct.sidebar.title": "Campaign\nHeadquarters",
    "ct.sidebar.desc":  "Our team answers your questions, handles your meeting requests and organises your exchanges with candidate Aimé BININGA.",
    "ct.lbl.address":   "Address",
    "ct.lbl.phone":     "Phone",
    "ct.lbl.email":     "Email",
    "ct.lbl.social":    "Social media",
    "ct.form.title":    "Send a message",
    "ct.form.firstname":"First name",
    "ct.form.lastname": "Last name",
    "ct.form.email":    "Email",
    "ct.form.subject":  "Subject",
    "ct.subj.general":  "General question",
    "ct.subj.meeting":  "Meeting request",
    "ct.subj.speech":   "Speaking engagement",
    "ct.subj.press":    "Press / Journalist",
    "ct.subj.partner":  "Partnership",
    "ct.form.message":  "Message",
    "ct.form.msg.ph":   "Your message...",
    "ct.form.send":     "📨 Send message",

    "nl.title":         "Stay informed",
    "nl.desc":          "Receive news, initiatives and updates from the Deputy directly in your inbox. No spam, one monthly letter.",
    "nl.btn":           "📩 Subscribe",
    "nl.legal":         "By subscribing, you agree to our",
    "nl.legal.link":    "privacy policy",
    "nl.ok":            "✅ Subscription confirmed, thank you for your support!",

    "ft.nav":           "Navigation",
    "ft.engage":        "Get involved",
    "ft.legal":         "Legal",
    "ft.volunteer":     "Become a volunteer",
    "ft.newsletter":    "Newsletter",
    "ft.press":         "Press",
    "ft.mentions":      "Legal notices",
    "ft.privacy":       "Privacy",
    "ft.copyright":     "© 2026 Aimé BININGA Campaign · Parti Congolais du Travail · All rights reserved",

    "chat.placeholder": "Ask DA your question…",
    "chat.send":        "Send",
    "chat.title":       "DA Assistant",
    "chat.greeting":    "Hello! I am DA, the virtual assistant. Ask me anything about Ange Aimé Wilfrid BININGA.",
  },

  es: {
    "nav.biography":    "Biografía",
    "nav.parcours":     "Trayectoria",
    "nav.publication":  "Publicación",
    "nav.programme":    "Programa",
    "nav.gallery":      "Galería",
    "nav.news":         "Noticias",
    "nav.contact":      "Contacto",
    "nav.audience":     "Audiencia",

    "hero.btn1":        "🤝 Unirse a la campaña",
    "hero.btn2":        "Nuestro programa",
    "hero.scroll":      "Descubrir",

    "about.tag":        "¿Quién es?",
    "about.title":      "Un hombre forjado por",
    "about.title.em":   "el terreno",
    "about.badge.lbl":  "Su circunscripción",

    "parcours.tag":     "Su trayectoria",
    "parcours.title":   "Una carrera construida sobre",
    "parcours.accent":  "la confianza",

    "prog.tag":         "Su programa",
    "prog.title":       "Un proyecto para",
    "prog.accent":      "Ewo y el Congo",

    "eng.tag":          "Contáctenos",
    "eng.title":        "¿Una reclamación o una",
    "eng.title.accent": "solicitud",
    "eng.desc":         "¿Tiene una reclamación o desea contactar al equipo del Diputado? Envíe su solicitud de audiencia y le responderemos a la brevedad.",
    "eng.card1.title":  "Solicitud de audiencia",
    "eng.card1.desc":   "Reúnase con el Diputado para exponer su situación",
    "eng.card2.title":  "Reclamación oficial",
    "eng.card2.desc":   "Denuncie un problema a su representante",
    "eng.card3.title":  "Tomar contacto",
    "eng.card3.desc":   "Conéctese con el equipo del Diputado de Ewo",
    "form.aud.title":   "Solicitud de audiencia al Diputado",
    "form.aud.sub":     "Explique el motivo de su solicitud, nuestro equipo le contactará en 48h",
    "form.firstname":   "Nombre *",
    "form.firstname.ph":"Su nombre",
    "form.lastname":    "Apellido *",
    "form.lastname.ph": "Su apellido",
    "form.address":     "Dirección *",
    "form.address.ph":  "Su dirección completa",
    "form.phone":       "Teléfono *",
    "form.email":       "Correo electrónico",
    "form.object":      "Asunto de la solicitud *",
    "form.obj.aud":     "Solicitud de audiencia",
    "form.obj.recl":    "Reclamación / Denuncia",
    "form.obj.q":       "Pregunta al Diputado",
    "form.obj.other":   "Otro",
    "form.reason":      "Motivo de la solicitud *",
    "form.reason.ph":   "Escriba su solicitud aquí. Explique el motivo, su situación y lo que espera del Diputado…",
    "form.submit.aud":  "📨 Enviar mi solicitud",
    "form.recl.badge":  "⚠️ Denuncia oficial",
    "form.recl.desc":   "Descripción del problema *",
    "form.recl.desc.ph":"Describa con precisión el problema a denunciar al Diputado…",
    "form.geo.title":   "📍 Localización del incidente",
    "form.geo.status":  "No localizado, haga clic para geolocalizar",
    "form.geo.btn":     "📍 Geolocalizar mi posición",
    "form.photo.lbl":   "📷 Foto del incidente",
    "form.photo.opt":   "(opcional, jpg/png, máx 3 MB)",

    "cta.title":        "Vote BININGA:\nla elección de la experiencia y el terreno",
    "cta.sub":          "Porque Ewo merece un hombre que conoce el Estado por dentro y el terreno de corazón.",
    "cta.btn1":         "📋 Solicitar audiencia",
    "cta.btn2":         "✉️ Contáctenos",
    "cta.btn3":         "📋 Leer el programa",

    "ct.tag":           "Escríbanos",
    "ct.title":         "Tome",
    "ct.accent":        "contacto",
    "ct.sidebar.title": "Sede Central\nde Campaña",
    "ct.sidebar.desc":  "Nuestro equipo responde sus preguntas, gestiona solicitudes de reunión y organiza intercambios con el candidato Aimé BININGA.",
    "ct.lbl.address":   "Dirección",
    "ct.lbl.phone":     "Teléfono",
    "ct.lbl.email":     "Correo",
    "ct.lbl.social":    "Redes sociales",
    "ct.form.title":    "Enviar un mensaje",
    "ct.form.firstname":"Nombre",
    "ct.form.lastname": "Apellido",
    "ct.form.email":    "Correo electrónico",
    "ct.form.subject":  "Asunto",
    "ct.subj.general":  "Pregunta general",
    "ct.subj.meeting":  "Solicitud de reunión",
    "ct.subj.speech":   "Intervención",
    "ct.subj.press":    "Prensa / Periodista",
    "ct.subj.partner":  "Alianza",
    "ct.form.message":  "Mensaje",
    "ct.form.msg.ph":   "Su mensaje...",
    "ct.form.send":     "📨 Enviar mensaje",

    "nl.title":         "Manténgase informado",
    "nl.desc":          "Reciba noticias e iniciativas del Diputado directamente en su correo. Sin spam, una carta mensual.",
    "nl.btn":           "📩 Suscribirse",
    "nl.legal":         "Al suscribirse, acepta nuestra",
    "nl.legal.link":    "política de privacidad",
    "nl.ok":            "✅ Suscripción confirmada, ¡gracias por su apoyo!",

    "ft.nav":           "Navegación",
    "ft.engage":        "Participar",
    "ft.legal":         "Legal",
    "ft.volunteer":     "Ser voluntario",
    "ft.newsletter":    "Boletín",
    "ft.press":         "Prensa",
    "ft.mentions":      "Aviso legal",
    "ft.privacy":       "Privacidad",
    "ft.copyright":     "© 2026 Campaña Aimé BININGA · Parti Congolais du Travail · Todos los derechos reservados",

    "chat.placeholder": "Haga su pregunta a DA…",
    "chat.send":        "Enviar",
    "chat.title":       "Asistente DA",
    "chat.greeting":    "¡Hola! Soy DA, el asistente virtual del sitio. Hágame preguntas sobre Ange Aimé Wilfrid BININGA.",
  },

  zh: {
    "nav.biography":    "人物简介",
    "nav.parcours":     "职业生涯",
    "nav.publication":  "出版作品",
    "nav.programme":    "竞选纲领",
    "nav.gallery":      "图片库",
    "nav.news":         "最新动态",
    "nav.contact":      "联系我们",
    "nav.audience":     "申请会见",

    "hero.btn1":        "🤝 加入竞选",
    "hero.btn2":        "查看纲领",
    "hero.scroll":      "了解更多",

    "about.tag":        "他是谁？",
    "about.title":      "一个在实践中磨砺的人",
    "about.title.em":   "实践",
    "about.badge.lbl":  "他的选区",

    "parcours.tag":     "职业历程",
    "parcours.title":   "建立于",
    "parcours.accent":  "信任之上的职业生涯",

    "prog.tag":         "竞选纲领",
    "prog.title":       "为",
    "prog.accent":      "埃沃与刚果的计划",

    "eng.tag":          "联系我们",
    "eng.title":        "投诉或",
    "eng.title.accent": "请求",
    "eng.desc":         "您有投诉、疑虑或希望联系议员团队？提交您的会见申请，我们将尽快回复您。",
    "eng.card1.title":  "申请会见",
    "eng.card1.desc":   "与议员会面，陈述您的情况",
    "eng.card2.title":  "正式投诉",
    "eng.card2.desc":   "向您的代表反映问题",
    "eng.card3.title":  "建立联系",
    "eng.card3.desc":   "与埃沃议员团队取得联系",
    "form.aud.title":   "向议员申请会见",
    "form.aud.sub":     "请说明申请目的，我们的团队将在48小时内与您联系",
    "form.firstname":   "名字 *",
    "form.firstname.ph":"您的名字",
    "form.lastname":    "姓氏 *",
    "form.lastname.ph": "您的姓氏",
    "form.address":     "地址 *",
    "form.address.ph":  "您的完整地址",
    "form.phone":       "电话 *",
    "form.email":       "电子邮件",
    "form.object":      "申请事项 *",
    "form.obj.aud":     "申请会见",
    "form.obj.recl":    "投诉 / 举报",
    "form.obj.q":       "向议员提问",
    "form.obj.other":   "其他",
    "form.reason":      "申请原因 *",
    "form.reason.ph":   "请在此填写您的申请。说明申请目的、您的情况以及对议员的期望…",
    "form.submit.aud":  "📨 提交申请",
    "form.recl.badge":  "⚠️ 正式举报",
    "form.recl.desc":   "问题描述 *",
    "form.recl.desc.ph":"请详细描述需要向议员反映的问题…",
    "form.geo.title":   "📍 事件位置",
    "form.geo.status":  "未定位，点击进行定位",
    "form.geo.btn":     "📍 定位我的位置",
    "form.photo.lbl":   "📷 事件照片",
    "form.photo.opt":   "（可选，jpg/png，最大3MB）",

    "cta.title":        "投票支持BININGA：\n经验与实干的选择",
    "cta.sub":          "因为埃沃值得一位了解国家内部运作、心系基层的人。",
    "cta.btn1":         "📋 申请会见",
    "cta.btn2":         "✉️ 联系我们",
    "cta.btn3":         "📋 阅读纲领",

    "ct.tag":           "给我们写信",
    "ct.title":         "取得",
    "ct.accent":        "联系",
    "ct.sidebar.title": "竞选总部",
    "ct.sidebar.desc":  "我们的团队回答您的问题，处理会面申请，并组织您与候选人艾梅·BININGA的交流。",
    "ct.lbl.address":   "地址",
    "ct.lbl.phone":     "电话",
    "ct.lbl.email":     "电子邮件",
    "ct.lbl.social":    "社交媒体",
    "ct.form.title":    "发送消息",
    "ct.form.firstname":"名字",
    "ct.form.lastname": "姓氏",
    "ct.form.email":    "电子邮件",
    "ct.form.subject":  "主题",
    "ct.subj.general":  "一般问题",
    "ct.subj.meeting":  "会面申请",
    "ct.subj.speech":   "发言邀请",
    "ct.subj.press":    "媒体 / 记者",
    "ct.subj.partner":  "合作",
    "ct.form.message":  "消息内容",
    "ct.form.msg.ph":   "您的消息...",
    "ct.form.send":     "📨 发送消息",

    "nl.title":         "保持关注",
    "nl.desc":          "直接在您的收件箱中接收议员的最新动态和举措。无垃圾邮件，每月一封简报。",
    "nl.btn":           "📩 订阅",
    "nl.legal":         "订阅即表示您同意我们的",
    "nl.legal.link":    "隐私政策",
    "nl.ok":            "✅ 订阅已确认，感谢您的支持！",

    "ft.nav":           "导航",
    "ft.engage":        "参与行动",
    "ft.legal":         "法律信息",
    "ft.volunteer":     "成为志愿者",
    "ft.newsletter":    "新闻简报",
    "ft.press":         "媒体",
    "ft.mentions":      "法律声明",
    "ft.privacy":       "隐私政策",
    "ft.copyright":     "© 2026 艾梅·BININGA竞选 · 刚果劳动党 · 保留所有权利",

    "chat.placeholder": "向DA提问…",
    "chat.send":        "发送",
    "chat.title":       "DA助手",
    "chat.greeting":    "您好！我是DA，网站虚拟助手。请向我提问有关安热·艾梅·威尔弗里德·BININGA的问题。",
  },

  ru: {
    "nav.biography":    "Биография",
    "nav.parcours":     "Карьера",
    "nav.publication":  "Публикация",
    "nav.programme":    "Программа",
    "nav.gallery":      "Галерея",
    "nav.news":         "Новости",
    "nav.contact":      "Контакт",
    "nav.audience":     "Аудиенция",

    "hero.btn1":        "🤝 Присоединиться к кампании",
    "hero.btn2":        "Наша программа",
    "hero.scroll":      "Узнать больше",

    "about.tag":        "Кто он?",
    "about.title":      "Человек, закалённый",
    "about.title.em":   "практикой",
    "about.badge.lbl":  "Его округ",

    "parcours.tag":     "Его карьера",
    "parcours.title":   "Карьера, построенная на",
    "parcours.accent":  "доверии",

    "prog.tag":         "Его программа",
    "prog.title":       "Проект для",
    "prog.accent":      "Эво и Конго",

    "eng.tag":          "Свяжитесь с нами",
    "eng.title":        "Жалоба или",
    "eng.title.accent": "запрос",
    "eng.desc":         "У вас есть жалоба или вы хотите связаться с командой Депутата? Отправьте запрос на аудиенцию, и мы ответим вам в кратчайшие сроки.",
    "eng.card1.title":  "Запрос на аудиенцию",
    "eng.card1.desc":   "Встретьтесь с Депутатом, чтобы изложить свою ситуацию",
    "eng.card2.title":  "Официальная жалоба",
    "eng.card2.desc":   "Сообщите о проблеме вашему представителю",
    "eng.card3.title":  "Установить контакт",
    "eng.card3.desc":   "Свяжитесь с командой Депутата Эво",
    "form.aud.title":   "Запрос на аудиенцию у Депутата",
    "form.aud.sub":     "Объясните цель вашего запроса, наша команда свяжется с вами в течение 48 часов",
    "form.firstname":   "Имя *",
    "form.firstname.ph":"Ваше имя",
    "form.lastname":    "Фамилия *",
    "form.lastname.ph": "Ваша фамилия",
    "form.address":     "Адрес *",
    "form.address.ph":  "Ваш полный адрес",
    "form.phone":       "Телефон *",
    "form.email":       "Эл. почта",
    "form.object":      "Тема запроса *",
    "form.obj.aud":     "Запрос на аудиенцию",
    "form.obj.recl":    "Жалоба / Сообщение",
    "form.obj.q":       "Вопрос Депутату",
    "form.obj.other":   "Другое",
    "form.reason":      "Причина запроса *",
    "form.reason.ph":   "Напишите ваш запрос здесь. Объясните цель, вашу ситуацию и ожидания от Депутата…",
    "form.submit.aud":  "📨 Отправить запрос",
    "form.recl.badge":  "⚠️ Официальное сообщение",
    "form.recl.desc":   "Описание проблемы *",
    "form.recl.desc.ph":"Точно опишите проблему, которую нужно сообщить Депутату…",
    "form.geo.title":   "📍 Место происшествия",
    "form.geo.status":  "Не определено, нажмите для геолокации",
    "form.geo.btn":     "📍 Определить моё местоположение",
    "form.photo.lbl":   "📷 Фото происшествия",
    "form.photo.opt":   "(необязательно, jpg/png, макс 3 МБ)",

    "cta.title":        "Голосуйте за BININGA:\nвыбор опыта и полевой работы",
    "cta.sub":          "Потому что Эво заслуживает человека, который знает государство изнутри и территорию от сердца.",
    "cta.btn1":         "📋 Запрос на аудиенцию",
    "cta.btn2":         "✉️ Связаться с нами",
    "cta.btn3":         "📋 Читать программу",

    "ct.tag":           "Написать нам",
    "ct.title":         "Установите",
    "ct.accent":        "контакт",
    "ct.sidebar.title": "Штаб\nкампании",
    "ct.sidebar.desc":  "Наша команда отвечает на вопросы, обрабатывает запросы о встречах и организует обмен с кандидатом Эме BININGA.",
    "ct.lbl.address":   "Адрес",
    "ct.lbl.phone":     "Телефон",
    "ct.lbl.email":     "Эл. почта",
    "ct.lbl.social":    "Соцсети",
    "ct.form.title":    "Отправить сообщение",
    "ct.form.firstname":"Имя",
    "ct.form.lastname": "Фамилия",
    "ct.form.email":    "Эл. почта",
    "ct.form.subject":  "Тема",
    "ct.subj.general":  "Общий вопрос",
    "ct.subj.meeting":  "Запрос о встрече",
    "ct.subj.speech":   "Выступление",
    "ct.subj.press":    "Пресса / Журналист",
    "ct.subj.partner":  "Партнёрство",
    "ct.form.message":  "Сообщение",
    "ct.form.msg.ph":   "Ваше сообщение...",
    "ct.form.send":     "📨 Отправить сообщение",

    "nl.title":         "Будьте в курсе",
    "nl.desc":          "Получайте новости и инициативы Депутата прямо на почту. Никакого спама, одно письмо в месяц.",
    "nl.btn":           "📩 Подписаться",
    "nl.legal":         "Подписываясь, вы соглашаетесь с нашей",
    "nl.legal.link":    "политикой конфиденциальности",
    "nl.ok":            "✅ Подписка подтверждена, спасибо за вашу поддержку!",

    "ft.nav":           "Навигация",
    "ft.engage":        "Участвовать",
    "ft.legal":         "Правовая информация",
    "ft.volunteer":     "Стать волонтёром",
    "ft.newsletter":    "Новостная рассылка",
    "ft.press":         "Пресса",
    "ft.mentions":      "Правовые уведомления",
    "ft.privacy":       "Конфиденциальность",
    "ft.copyright":     "© 2026 Кампания Эме BININGA · Parti Congolais du Travail · Все права защищены",

    "chat.placeholder": "Задайте вопрос DA…",
    "chat.send":        "Отправить",
    "chat.title":       "Ассистент DA",
    "chat.greeting":    "Здравствуйте! Я DA, виртуальный помощник сайта. Задайте мне вопросы об Анж Эме Вильфрид BININGA.",
  }
};

// ── Langue courante ────────────────────────────────────────────────────────────
let _currentLang = localStorage.getItem("bininga_lang") || "fr";

function t(key) {
  return (I18N[_currentLang] && I18N[_currentLang][key]) ||
         (I18N["fr"] && I18N["fr"][key]) || key;
}

// ── Appliquer toutes les traductions ──────────────────────────────────────────
function applyI18n(lang) {
  _currentLang = lang;
  localStorage.setItem("bininga_lang", lang);
  document.documentElement.lang = lang;

  // Mettre à jour tous les éléments marqués data-i18n
  document.querySelectorAll("[data-i18n]").forEach(el => {
    const key = el.getAttribute("data-i18n");
    const attr = el.getAttribute("data-i18n-attr");
    const val = t(key);
    if (attr) {
      el.setAttribute(attr, val);
    } else {
      el.textContent = val;
    }
  });

  // Placeholders (data-i18n-ph)
  document.querySelectorAll("[data-i18n-ph]").forEach(el => {
    el.placeholder = t(el.getAttribute("data-i18n-ph"));
  });

  // Mettre à jour le sélecteur de langue visuel
  document.querySelectorAll(".lang-btn").forEach(btn => {
    btn.classList.toggle("lang-active", btn.dataset.lang === lang);
  });

  // Chat greeting si la fenêtre chat est ouverte
  const chatGreeting = document.getElementById("chat-greeting");
  if (chatGreeting) chatGreeting.textContent = t("chat.greeting");
  const chatInput = document.getElementById("chat-input");
  if (chatInput) chatInput.placeholder = t("chat.placeholder");
  const chatSendBtn = document.getElementById("chat-send-btn");
  if (chatSendBtn) chatSendBtn.textContent = t("chat.send");
  const chatTitle = document.getElementById("chat-title");
  if (chatTitle) chatTitle.textContent = t("chat.title");

  // Traduction du contenu dynamique (injecté par index.js depuis data.json)
  if (typeof applyDynLang === "function") applyDynLang(lang);
}

// ── Init au chargement ────────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
  applyI18n(_currentLang);
});
