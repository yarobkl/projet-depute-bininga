import SwiftUI

private enum BiningaStyle {
    static let background = Color(red: 10 / 255, green: 10 / 255, blue: 10 / 255)
    static let text = Color(red: 244 / 255, green: 240 / 255, blue: 234 / 255)
    static let accent = Color(red: 122 / 255, green: 28 / 255, blue: 46 / 255)
    static let red = Color(red: 0.88, green: 0.12, blue: 0.22)
    static let site = URL(string: "https://projet-depute-bininga.vercel.app")!
}

private struct Publication: Decodable, Hashable {
    let title: String
    var subtitle: String?, desc: String?, text1: String?, text2: String?, quote: String?
    var image: String?, date: String?, source: String?, sourceUrl: String?
    var bodyText: String { [subtitle, desc, text1, quote, text2].compactMap { $0 }.joined(separator: "\n\n") }
}

private struct PublicContent: Decodable {
    struct News: Decodable {
        var slides: [Publication]?, vedettes: [Publication]?, cards: [Publication]?
    }
    struct Programme: Decodable {
        struct Axis: Decodable { let title: String; var text: String?, points: [String]? }
        var axes: [Axis]?
    }
    let actus: News
    let programme: Programme
}

private enum SectionTab: String, CaseIterable {
    case home = "Accueil", news = "Actualités", requests = "Demandes", more = "Plus"
    var icon: String {
        switch self {
        case .home: "house"
        case .news: "newspaper"
        case .requests: "folder"
        case .more: "ellipsis"
        }
    }
}

struct PublicTabs: View {
    @State private var selected = SectionTab.home
    @State private var filter = "À la une"
    @State private var content: PublicContent?
    @State private var warning: String?
    @State private var loading = false
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @Environment(\.dynamicTypeSize) private var textSize
    @Namespace private var selection

    var body: some View {
        TabView(selection: $selected) {
            home.tag(SectionTab.home)
            news.tag(SectionTab.news)
            requests.tag(SectionTab.requests)
            more.tag(SectionTab.more)
        }
        .tabViewStyle(.page(indexDisplayMode: .never))
        .safeAreaInset(edge: .bottom, spacing: 0) { tabBar }
        .background(BiningaStyle.background.ignoresSafeArea())
        .foregroundStyle(BiningaStyle.text)
        .tint(BiningaStyle.accent)
        .toolbar(.hidden, for: .navigationBar)
        .task { await refresh() }
    }

    private var home: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                homeHero
                VStack(alignment: .leading, spacing: 7) {
                    Text("L’ENGAGEMENT").font(.caption2.weight(.semibold))
                        .tracking(1).foregroundStyle(BiningaStyle.red)
                    Text("Un homme de terrain, de conviction et de résultats.")
                        .font(.system(.title3, design: .serif).weight(.semibold))
                    Text("Une vie au service du peuple congolais et de la Cuvette-Ouest.")
                        .font(.subheadline).foregroundStyle(BiningaStyle.text.opacity(0.7))
                }
                .card()
                VStack(spacing: 9) {
                    action("Demander une audience", icon: "calendar", route: .audience, primary: true)
                    action("Suivre ma demande", icon: "doc.text.magnifyingglass", route: .tracking(""))
                }
                if let item = content?.actus.slides?.first {
                    HStack {
                        Text("À la une").font(.headline)
                        Spacer()
                        Button("Tout voir") { selected = .news }.font(.subheadline)
                    }.padding(.top, 6)
                    publicationLink(item, featured: false, category: "À LA UNE")
                }
            }
            .padding(.horizontal, 20).padding(.top, 8).padding(.bottom, 20)
            .frame(maxWidth: 640).frame(maxWidth: .infinity)
        }
        .scrollIndicators(.hidden)
        .refreshable { await refresh() }
    }

    private var homeHero: some View {
        VStack(alignment: .leading, spacing: 0) {
            VStack(alignment: .leading, spacing: 4) {
                Text("BININGA")
                    .font(.system(.title, design: .serif).weight(.semibold)).tracking(-0.5)
                Text("Ange Aimé Wilfrid BININGA").font(.caption.weight(.semibold))
                Text("Député d’Ewo, République du Congo")
                    .font(.caption2).foregroundStyle(BiningaStyle.text.opacity(0.8))
                rule.padding(.top, 8)
            }
            .padding(.horizontal, 16).padding(.top, 14)
            Spacer(minLength: 30)
            VStack(alignment: .leading, spacing: 10) {
                Text("Ewo, au cœur de\nnotre action")
                    .font(.system(.title, design: .serif).weight(.semibold).italic())
                    .tracking(-0.5).fixedSize(horizontal: false, vertical: true)
                rule
            }.padding(16)
        }
        .frame(maxWidth: .infinity, minHeight: textSize.isAccessibilitySize ? 420 : 300, alignment: .leading)
        .background {
            GeometryReader { geometry in
                Image("Ewo").resizable().scaledToFill()
                    .frame(width: geometry.size.width, height: geometry.size.height)
                    .clipped()
                    .overlay {
                        LinearGradient(stops: [
                            .init(color: BiningaStyle.background.opacity(0.97), location: 0),
                            .init(color: BiningaStyle.background.opacity(0.7), location: 0.28),
                            .init(color: .clear, location: 0.48),
                            .init(color: BiningaStyle.background.opacity(0.9), location: 1)
                        ], startPoint: .top, endPoint: .bottom)
                    }
            }
        }
        .clipShape(RoundedRectangle(cornerRadius: 18, style: .continuous))
    }

    private var news: some View {
        page("Actualités", subtitle: "L’actualité du député et d’Ewo") {
            Picker("Rubrique", selection: $filter) {
                ForEach(["À la une", "Terrain", "Programme"], id: \.self) { Text($0) }
            }.pickerStyle(.segmented)
            if let warning {
                VStack(alignment: .leading, spacing: 6) {
                    Text(warning).font(.footnote)
                    Button("Actualiser") { Task { await refresh() } }.disabled(loading)
                }
            }
            if let content {
                if filter == "Programme" {
                    ForEach(Array((content.programme.axes ?? []).enumerated()), id: \.offset) { _, axis in
                        VStack(alignment: .leading, spacing: 8) {
                            Text(axis.title).font(.headline)
                            if let text = axis.text { Text(text).font(.subheadline) }
                            ForEach(Array((axis.points ?? []).enumerated()), id: \.offset) { _, point in
                                Label(point, systemImage: "circle.fill").font(.footnote)
                            }
                        }.card()
                    }
                } else {
                    let articles = filter == "Terrain" ? content.actus.cards ?? [] : (content.actus.slides ?? []) + (content.actus.vedettes ?? [])
                    if articles.isEmpty { Text("Aucune publication dans cette rubrique.").font(.subheadline) }
                    ForEach(Array(articles.enumerated()), id: \.offset) { index, item in
                        publicationLink(item, featured: index == 0, category: filter.uppercased())
                    }
                }
            } else if loading { ProgressView("Chargement des actualités") }
        }
    }

    private var requests: some View {
        page("Mes démarches", subtitle: "Adressez une demande au cabinet et consultez son suivi.") {
            ViewThatFits(in: .horizontal) {
                HStack(alignment: .top, spacing: 12) { requestTiles }
                VStack(spacing: 12) { requestTiles }
            }
            VStack(alignment: .leading, spacing: 10) {
                Text("Vous avez déjà une référence ?").font(.headline)
                Text("Une demande déposée sur le site ou sur l’application se suit avec le même numéro.")
                    .font(.subheadline).foregroundStyle(BiningaStyle.text.opacity(0.7))
                action("Suivre ma demande", icon: "doc.text.magnifyingglass", route: .tracking(""))
            }.padding(.top, 10)
        }
    }

    @ViewBuilder private var requestTiles: some View {
        requestTile("Audience", subtitle: "Rencontrez le député pour exposer votre situation.", icon: "calendar", route: .audience, primary: true)
        requestTile("Réclamation", subtitle: "Signalez un problème auprès de votre représentant.", icon: "bubble.left", route: .complaint)
    }

    private var more: some View {
        page("Mon espace", subtitle: "Le suivi de vos demandes, sans compte à créer.") {
            VStack(alignment: .leading, spacing: 12) {
                Image(systemName: "doc.text.magnifyingglass").font(.title2)
                Text("Retrouver un dossier").font(.system(.title3, design: .serif).weight(.semibold))
                Text("Munissez-vous de la référence reçue après l’envoi de votre demande.")
                    .font(.subheadline).foregroundStyle(BiningaStyle.text.opacity(0.7))
                action("Saisir ma référence", icon: "magnifyingglass", route: .tracking(""), primary: true)
            }.card()
            Link(destination: BiningaStyle.site) {
                HStack { Label("Le site BININGA", systemImage: "safari"); Spacer(); Image(systemName: "arrow.up.right") }
                    .font(.subheadline).padding(.vertical, 14)
            }
            action("Suivre ma demande", icon: "folder", route: .tracking(""))
        }
    }

    private var rule: some View {
        RoundedRectangle(cornerRadius: 1).fill(BiningaStyle.red).frame(width: 30, height: 3).accessibilityHidden(true)
    }

    private var tabBar: some View {
        HStack(spacing: 0) {
            ForEach(SectionTab.allCases, id: \.self) { tab in
                Button {
                    withAnimation(reduceMotion ? nil : .easeInOut(duration: 0.22)) { selected = tab }
                } label: {
                    VStack(spacing: 4) {
                        Image(systemName: tab.icon).font(.system(size: 18, weight: .regular))
                        Text(tab.rawValue).font(.caption2.weight(selected == tab ? .semibold : .regular))
                    }
                    .frame(maxWidth: .infinity, minHeight: 46)
                    .padding(.vertical, 3)
                    .background {
                        if selected == tab {
                            Capsule().fill(BiningaStyle.accent).matchedGeometryEffect(id: "selected", in: selection)
                        }
                    }
                    .contentShape(Rectangle())
                }
                .buttonStyle(.plain)
                .accessibilityLabel(tab.rawValue)
                .accessibilityAddTraits(selected == tab ? .isSelected : [])
            }
        }
        .padding(4)
        .background(.ultraThinMaterial, in: Capsule())
        .overlay { Capsule().strokeBorder(.white.opacity(0.1), lineWidth: 0.5) }
        .padding(.horizontal, 20).padding(.top, 8).padding(.bottom, 6)
    }

    private func page<Content: View>(_ title: String, subtitle: String, @ViewBuilder contents: () -> Content) -> some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                VStack(alignment: .leading, spacing: 7) {
                    Text("BININGA").font(.system(.subheadline, design: .serif).weight(.semibold))
                    Text(title).font(.system(.title, design: .serif).weight(.semibold)).tracking(-0.4)
                        .accessibilityAddTraits(.isHeader)
                    Text(subtitle).font(.footnote).foregroundStyle(BiningaStyle.text.opacity(0.7))
                    rule.padding(.top, 5)
                }.padding(.bottom, 3)
                contents()
            }
            .padding(.horizontal, 20).padding(.top, 14).padding(.bottom, 20)
            .frame(maxWidth: 640).frame(maxWidth: .infinity)
        }.scrollIndicators(.hidden)
    }

    private func action(_ name: String, icon: String, route: Route, primary: Bool = false) -> some View {
        NavigationLink(value: route) {
            HStack(spacing: 10) {
                Image(systemName: icon).frame(width: 22)
                Text(name).font(.subheadline.weight(.semibold))
                Spacer(minLength: 6)
                Image(systemName: "chevron.right").font(.caption.weight(.semibold))
            }
            .frame(minHeight: 24).padding(.horizontal, 14).padding(.vertical, 11)
            .background(primary ? BiningaStyle.accent : Color.white.opacity(0.035), in: RoundedRectangle(cornerRadius: 12))
            .overlay { RoundedRectangle(cornerRadius: 12).strokeBorder(BiningaStyle.text.opacity(primary ? 0.1 : 0.35), lineWidth: 0.5) }
            .contentShape(RoundedRectangle(cornerRadius: 12))
        }.buttonStyle(.plain)
    }

    private func requestTile(_ title: String, subtitle: String, icon: String, route: Route, primary: Bool = false) -> some View {
        NavigationLink(value: route) {
            VStack(alignment: .leading, spacing: 10) {
                Image(systemName: icon).font(.title2)
                Text(title).font(.system(.title3, design: .serif).weight(.semibold))
                Text(subtitle).font(.footnote).foregroundStyle(BiningaStyle.text.opacity(0.8))
                    .fixedSize(horizontal: false, vertical: true)
                Image(systemName: "chevron.right").font(.caption).frame(maxWidth: .infinity, alignment: .trailing)
            }
            .frame(minWidth: 115, maxWidth: .infinity, minHeight: 145, alignment: .topLeading)
            .padding(14)
            .background(primary ? BiningaStyle.accent : .white.opacity(0.035), in: RoundedRectangle(cornerRadius: 16))
            .overlay { RoundedRectangle(cornerRadius: 16).strokeBorder(.white.opacity(0.2), lineWidth: 0.5) }
        }.buttonStyle(.plain)
        .accessibilityLabel(primary ? "Demander une audience" : "Déposer une réclamation")
    }

    private func publicationLink(_ item: Publication, featured: Bool, category: String) -> some View {
        NavigationLink {
            ScrollView {
                VStack(alignment: .leading, spacing: 16) {
                    publicationPhoto(item).aspectRatio(16 / 9, contentMode: .fit).clipShape(RoundedRectangle(cornerRadius: 14))
                    Text(item.title).font(.system(.title2, design: .serif).weight(.semibold))
                    if let date = item.date { Text(date).font(.caption).foregroundStyle(.secondary) }
                    Text(item.bodyText).font(.body)
                    if let raw = item.sourceUrl, let url = URL(string: raw), url.scheme == "https" {
                        Link(item.source ?? "Lire la source", destination: url)
                    }
                }.padding(20).frame(maxWidth: 640).frame(maxWidth: .infinity)
            }
            .navigationTitle("Actualité").navigationBarTitleDisplayMode(.inline)
            .toolbar(.visible, for: .navigationBar)
        } label: {
            if featured || textSize.isAccessibilitySize {
                VStack(alignment: .leading, spacing: 0) {
                    publicationPhoto(item).aspectRatio(16 / 9, contentMode: .fit)
                    publicationSummary(item, category: category).padding(14)
                }.background(.white.opacity(0.045), in: RoundedRectangle(cornerRadius: 16))
                    .clipShape(RoundedRectangle(cornerRadius: 16))
                    .overlay { RoundedRectangle(cornerRadius: 16).strokeBorder(.white.opacity(0.16), lineWidth: 0.5) }
            } else {
                HStack(alignment: .top, spacing: 12) {
                    publicationPhoto(item).frame(width: 88, height: 96).clipShape(RoundedRectangle(cornerRadius: 9))
                    publicationSummary(item, category: category)
                }.card(padding: 10)
            }
        }.buttonStyle(.plain)
    }

    private func publicationSummary(_ item: Publication, category: String) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(category).font(.system(.caption2).weight(.semibold)).tracking(0.5).foregroundStyle(BiningaStyle.text.opacity(0.65))
            Text(item.title).font(.system(.headline, design: .serif)).lineLimit(3)
                .fixedSize(horizontal: false, vertical: true)
            if let date = item.date {
                Label(date, systemImage: "calendar").font(.caption2).foregroundStyle(BiningaStyle.text.opacity(0.6))
            }
        }.frame(maxWidth: .infinity, alignment: .leading)
    }

    private func publicationPhoto(_ item: Publication) -> some View {
        Color.white.opacity(0.04).overlay {
            if let raw = item.image, !raw.isEmpty,
               let url = URL(string: raw, relativeTo: BiningaStyle.site)?.absoluteURL, url.scheme == "https" {
                GeometryReader { geometry in
                    AsyncImage(url: url) { phase in
                        if let image = phase.image {
                            image.resizable().scaledToFill()
                                .frame(width: geometry.size.width, height: geometry.size.height).clipped()
                        } else if phase.error != nil {
                            Image(systemName: "photo").frame(maxWidth: .infinity, maxHeight: .infinity).foregroundStyle(.secondary)
                        } else {
                            ProgressView().frame(maxWidth: .infinity, maxHeight: .infinity)
                        }
                    }
                }
            }
        }.clipped().accessibilityHidden(true)
    }

    @MainActor private func refresh() async {
        guard !loading else { return }
        loading = true
        defer { loading = false }
        if content == nil, let file = Bundle.main.url(forResource: "PublicContent", withExtension: "json"),
           let data = try? Data(contentsOf: file) {
            content = try? JSONDecoder().decode(PublicContent.self, from: data)
        }
        do {
            let request = URLRequest(url: BiningaStyle.site.appendingPathComponent("api/load"), timeoutInterval: 12)
            let (data, response) = try await URLSession.shared.data(for: request)
            guard let http = response as? HTTPURLResponse, http.statusCode == 200 else { throw URLError(.badServerResponse) }
            content = try JSONDecoder().decode(PublicContent.self, from: data)
            warning = nil
        } catch {
            if !Task.isCancelled {
                warning = content == nil ? "Contenu indisponible. Réessayez dans un instant." : "Vous consultez les actualités enregistrées. La connexion au site est indisponible."
            }
        }
    }
}

private extension View {
    func card(padding: CGFloat = 16) -> some View {
        self.frame(maxWidth: .infinity, alignment: .leading).padding(padding)
            .background(.white.opacity(0.045), in: RoundedRectangle(cornerRadius: 16))
            .overlay { RoundedRectangle(cornerRadius: 16).strokeBorder(.white.opacity(0.16), lineWidth: 0.5) }
    }
}
