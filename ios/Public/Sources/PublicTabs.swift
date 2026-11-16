import SwiftUI
import UIKit
import UserNotifications

enum BiningaStyle {
    static let background = Color(red: 245 / 255, green: 242 / 255, blue: 237 / 255)
    static let text = Color(red: 37 / 255, green: 35 / 255, blue: 33 / 255)
    static let secondary = Color(red: 113 / 255, green: 107 / 255, blue: 101 / 255)
    static let border = Color(red: 227 / 255, green: 221 / 255, blue: 213 / 255)
    static let surface = Color.white
    static let cream = Color(red: 244 / 255, green: 240 / 255, blue: 234 / 255)
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
    @State private var showsNotifications = false
    @State private var content: PublicContent?
    @State private var warning: String?
    @State private var loading = false
    @Environment(\.dynamicTypeSize) private var textSize
    @ScaledMetric(relativeTo: .subheadline) private var nameSize = 15
    @ScaledMetric(relativeTo: .footnote) private var roleSize = 13
    @ScaledMetric(relativeTo: .title2) private var heroTitleSize = 22

    var body: some View {
        TabView(selection: $selected) {
            PublicNavigation {
                home
                    .navigationTitle("BININGA")
                    .toolbar {
                        ToolbarItem(placement: .topBarTrailing) {
                            Button("Notifications", systemImage: "bell") { showsNotifications = true }
                        }
                    }
                    .navigationBarTitleDisplayMode(.large)
            }
                .tabItem { Label(SectionTab.home.rawValue, systemImage: SectionTab.home.icon) }
                .tag(SectionTab.home)
            PublicNavigation {
                news
                    .navigationTitle("Actualités")
                    .navigationBarTitleDisplayMode(.large)
            }
                .tabItem { Label(SectionTab.news.rawValue, systemImage: SectionTab.news.icon) }
                .tag(SectionTab.news)
            PublicNavigation {
                requests
                    .navigationTitle("Mes démarches")
                    .navigationBarTitleDisplayMode(.large)
            }
                .tabItem { Label(SectionTab.requests.rawValue, systemImage: SectionTab.requests.icon) }
                .tag(SectionTab.requests)
            PublicNavigation {
                more
                    .navigationTitle("Mon espace")
                    .navigationBarTitleDisplayMode(.large)
            }
                .tabItem { Label(SectionTab.more.rawValue, systemImage: SectionTab.more.icon) }
                .tag(SectionTab.more)
        }
        // Match QR Permanent: let iOS own tab dimensions, safe areas and glass interaction.
        .tabViewStyle(.automatic)
        .background(BiningaStyle.background.ignoresSafeArea())
        .foregroundStyle(BiningaStyle.text)
        .tint(BiningaStyle.accent)
        .sheet(isPresented: $showsNotifications) { NotificationInbox() }
        .task { await refresh() }
    }

    private var home: some View {
        MainLayoutTemplate(spacing: 16) {
                homePortrait
                VStack(alignment: .leading, spacing: 16) {
                    VStack(alignment: .leading, spacing: 7) {
                        Text("L’ENGAGEMENT").font(.caption2.weight(.semibold))
                            .tracking(1).foregroundStyle(BiningaStyle.red)
                        Text("Un homme de terrain, de conviction et de résultats.")
                            .font(.system(.title3).weight(.semibold))
                        Text("Une vie au service du peuple congolais et de la Cuvette-Ouest.")
                            .font(.subheadline).foregroundStyle(BiningaStyle.secondary)
                    }
                    VStack(spacing: 12) {
                        action("Demander une audience", icon: "calendar", route: .audience, primary: true)
                        Button {
                            filter = "Programme"
                            selected = .news
                        } label: {
                            Label("Lire le programme", systemImage: "book.closed")
                                .frame(maxWidth: .infinity, minHeight: 24)
                                .padding(.vertical, 2)
                        }
                        .font(.headline)
                        .controlSize(.large)
                        .buttonBorderShape(.roundedRectangle(radius: 14))
                        .buttonStyle(.bordered)
                    }
                    if !terrainPublications.isEmpty {
                        Text("Sur le terrain").font(.title2.bold())
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .padding(.top, 8)
                        ScrollView(.horizontal) {
                            LazyHStack(alignment: .top, spacing: 12) {
                                ForEach(Array(terrainPublications.enumerated()), id: \.offset) { _, item in
                                    publicationLink(item, featured: true, category: "SUR LE TERRAIN")
                                        .containerRelativeFrame(.horizontal)
                                }
                            }
                            .scrollTargetLayout()
                        }
                        .scrollTargetBehavior(.viewAligned)
                        .scrollIndicators(.hidden)
                        .accessibilityLabel("Les actions sur le terrain")
                    }
                }
                .frame(maxWidth: .infinity)
        }
        .refreshable { await refresh() }
    }

    private var homePortrait: some View {
        ViewThatFits(in: .horizontal) {
            HStack(alignment: .center, spacing: 16) {
                portraitPhoto.frame(width: 116, height: 172)
                portraitIdentity.frame(minWidth: 150, maxWidth: .infinity, alignment: .leading)
            }
            VStack(alignment: .leading, spacing: 16) {
                portraitPhoto.frame(height: 220)
                portraitIdentity
            }
        }
        .card()
    }

    private var portraitPhoto: some View {
        GeometryReader { geometry in
            Image("BiningaPortrait")
                .resizable().scaledToFill()
                .frame(width: geometry.size.width, height: geometry.size.height, alignment: .top)
                .clipped()
        }
        .clipShape(RoundedRectangle(cornerRadius: 12))
        .accessibilityLabel("Portrait d’Ange Aimé Wilfrid BININGA")
    }

    private var portraitIdentity: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Ange Aimé Wilfrid BININGA").font(.title3.bold())
            Text("Député d’Ewo, République du Congo")
                .font(.subheadline).foregroundStyle(BiningaStyle.secondary)
        }
        .fixedSize(horizontal: false, vertical: true)
    }

    private var terrainPublications: [Publication] {
        (content?.actus.cards ?? []).filter {
            let title = $0.title.folding(options: [.diacriticInsensitive, .caseInsensitive], locale: Locale(identifier: "fr"))
            return title.contains("ewo") || title.contains("cuvette") || title.contains("lebankaya")
        }
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
                    .font(.subheadline).foregroundStyle(BiningaStyle.secondary)
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
                Text("Retrouver un dossier").font(.system(.title3).weight(.semibold))
                Text("Munissez-vous de la référence reçue après l’envoi de votre demande.")
                    .font(.subheadline).foregroundStyle(BiningaStyle.secondary)
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

    private func page<Content: View>(_ title: String, subtitle: String, @ViewBuilder contents: () -> Content) -> some View {
        MainLayoutTemplate {
            Text(subtitle).font(.subheadline).foregroundStyle(BiningaStyle.secondary)
            contents()
        }
    }

    private func action(_ name: String, icon: String, route: Route, primary: Bool = false) -> some View {
        NavigationLink(value: route) {
            Label(name, systemImage: icon)
                .frame(maxWidth: .infinity, minHeight: 24)
                .padding(.vertical, 2)
        }
        .font(.headline)
        .controlSize(.large)
        .buttonBorderShape(.roundedRectangle(radius: 14))
        .modifier(NativeActionStyle(primary: primary))
    }

    private func requestTile(_ title: String, subtitle: String, icon: String, route: Route, primary: Bool = false) -> some View {
        NavigationLink(value: route) {
            VStack(alignment: .leading, spacing: 10) {
                Image(systemName: icon).font(.title2)
                Text(title).font(.system(.title3).weight(.semibold))
                Text(subtitle).font(.footnote).foregroundStyle(primary ? Color.white.opacity(0.9) : BiningaStyle.secondary)
                    .fixedSize(horizontal: false, vertical: true)
                Image(systemName: "chevron.right").font(.caption).frame(maxWidth: .infinity, alignment: .trailing)
            }
            .frame(minWidth: 115, maxWidth: .infinity, minHeight: 145, alignment: .topLeading)
            .padding(14)
            .foregroundStyle(primary ? Color.white : BiningaStyle.text)
            .background(primary ? BiningaStyle.accent : BiningaStyle.surface, in: RoundedRectangle(cornerRadius: 16))
            .overlay { RoundedRectangle(cornerRadius: 16).strokeBorder(BiningaStyle.border, lineWidth: 0.5) }
        }.buttonStyle(.plain)
        .accessibilityLabel(primary ? "Demander une audience" : "Déposer une réclamation")
    }

    private func publicationLink(_ item: Publication, featured: Bool, category: String) -> some View {
        NavigationLink {
            ScrollView {
                VStack(alignment: .leading, spacing: 16) {
                    publicationPhoto(item).aspectRatio(16 / 9, contentMode: .fit).clipShape(RoundedRectangle(cornerRadius: 14))
                    Text(item.title).font(.system(.title2).weight(.semibold))
                    if let date = item.date { Text(date).font(.caption).foregroundStyle(.secondary) }
                    Text(item.bodyText).font(.body)
                    if let raw = item.sourceUrl, let url = URL(string: raw), url.scheme == "https" {
                        Link(item.source ?? "Lire la source", destination: url)
                    }
                }.padding(20).frame(maxWidth: 640).frame(maxWidth: .infinity)
            }
.background(BiningaStyle.background)
            .navigationTitle("Actualité").navigationBarTitleDisplayMode(.inline)
            .toolbar(.visible, for: .navigationBar)
        } label: {
            if featured || textSize.isAccessibilitySize {
                VStack(alignment: .leading, spacing: 0) {
                    publicationPhoto(item).aspectRatio(16 / 9, contentMode: .fit)
                    publicationSummary(item, category: category).padding(14)
                }.background(BiningaStyle.surface, in: RoundedRectangle(cornerRadius: 16))
                    .clipShape(RoundedRectangle(cornerRadius: 16)).contentShape(Rectangle())
                    .overlay { RoundedRectangle(cornerRadius: 16).strokeBorder(BiningaStyle.border, lineWidth: 0.5) }
            } else {
                HStack(alignment: .top, spacing: 12) {
                    publicationPhoto(item).frame(width: 88, height: 96).clipShape(RoundedRectangle(cornerRadius: 9))
                    publicationSummary(item, category: category)
                }.card(padding: 10).contentShape(Rectangle())
            }
        }.buttonStyle(.plain)
    }

    private func publicationSummary(_ item: Publication, category: String) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(category).font(.system(.caption2).weight(.semibold)).tracking(0.5).foregroundStyle(BiningaStyle.secondary)
            Text(item.title).font(.system(.headline)).lineLimit(3)
                .fixedSize(horizontal: false, vertical: true)
            if let date = item.date {
                Label(date, systemImage: "calendar").font(.caption2).foregroundStyle(BiningaStyle.secondary)
            }
        }.frame(maxWidth: .infinity, alignment: .leading)
    }

    private func publicationPhoto(_ item: Publication) -> some View {
        BiningaStyle.border.overlay {
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
        }.clipped().contentShape(Rectangle()).allowsHitTesting(false).accessibilityHidden(true)
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
            .background(BiningaStyle.surface, in: RoundedRectangle(cornerRadius: 16))
            .overlay { RoundedRectangle(cornerRadius: 16).strokeBorder(BiningaStyle.border, lineWidth: 0.5) }
    }
}


// Shared page geometry. The native TabView owns the bottom safe area.
// Only backgrounds may extend outside the system safe area.
private struct MainLayoutTemplate<Content: View>: View {
    private let content: Content
    private let horizontalPadding: CGFloat
    private let topPadding: CGFloat
    private let spacing: CGFloat

    init(horizontalPadding: CGFloat = 16, topPadding: CGFloat = 4,
         spacing: CGFloat = 20, @ViewBuilder content: () -> Content) {
        self.horizontalPadding = horizontalPadding
        self.topPadding = topPadding
        self.spacing = spacing
        self.content = content()
    }

    var body: some View {
        ZStack {
            BiningaStyle.background
                .ignoresSafeArea()
            ScrollView {
                LazyVStack(alignment: .leading, spacing: spacing) {
                    content
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(.horizontal, horizontalPadding)
                .padding(.top, topPadding)
                .padding(.bottom, 20)
            }
        }
    }
}

private struct NativeActionStyle: ViewModifier {
    let primary: Bool
    @ViewBuilder func body(content: Content) -> some View {
        if primary {
            content.buttonStyle(.borderedProminent)
        } else {
            content.buttonStyle(.bordered)
        }
    }
}

private struct NotificationInbox: View {
    @Environment(\.dismiss) private var dismiss
    @State private var notifications: [UNNotification] = []
    @StateObject private var push = PushService.shared

    var body: some View {
        NavigationStack {
            Group {
                if notifications.isEmpty {
                    ContentUnavailableView {
                        Label("Aucune notification", systemImage: "bell")
                    } description: {
                        Text(push.message)
                    }
                } else {
                    List(notifications, id: \.request.identifier) { notification in
                        VStack(alignment: .leading, spacing: 6) {
                            Text(notification.request.content.title).font(.headline)
                            Text(notification.request.content.body).font(.body)
                            Text(notification.date, style: .date).font(.caption).foregroundStyle(.secondary)
                        }
                    }
                }
            }
            .safeAreaInset(edge: .bottom) {
                VStack(spacing: 8) {
                    if push.denied {
                        Button("Ouvrir les réglages") { if let url = URL(string: UIApplication.openSettingsURLString) { UIApplication.shared.open(url) } }
                    } else {
                        Button("Activer ou actualiser les notifications") { Task { await push.requestPermission() } }.disabled(push.busy)
                    }
                    Text(push.message).font(.footnote).foregroundStyle(.secondary)
                }.padding().frame(maxWidth: .infinity).background(.regularMaterial)
            }
            .navigationTitle("Notifications")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .confirmationAction) {
                    Button("Fermer") { dismiss() }
                }
            }
        }
        .tint(BiningaStyle.accent)
        .task {
            notifications = await withCheckedContinuation { continuation in
                UNUserNotificationCenter.current().getDeliveredNotifications {
                    continuation.resume(returning: $0.sorted { $0.date > $1.date })
                }
            }
        }
    }
}
