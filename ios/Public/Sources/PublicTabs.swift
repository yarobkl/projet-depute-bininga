import SwiftUI

private let site = URL(string: "https://projet-depute-bininga.vercel.app")!
private let cream = Color(red: 244 / 255, green: 240 / 255, blue: 234 / 255)
private let charcoal = Color(red: 10 / 255, green: 10 / 255, blue: 10 / 255)
private let indicator = Color(red: 0.88, green: 0.12, blue: 0.22)
private let wine = Color(red: 122 / 255, green: 28 / 255, blue: 46 / 255)

private struct Publication: Decodable, Hashable {
    let title: String
    var subtitle: String?, desc: String?, text1: String?, text2: String?, quote: String?
    var image: String?, date: String?, source: String?, sourceUrl: String?
    var bodyText: String { [subtitle,desc,text1,quote,text2].compactMap { $0 }.joined(separator: "\n\n") }
}
private struct PublicContent: Decodable {
    struct News: Decodable { var slides: [Publication]?, vedettes: [Publication]?, cards: [Publication]? }
    struct Programme: Decodable {
        struct Axis: Decodable { let title: String; var text: String?, points: [String]? }
        var axes: [Axis]?
    }
    let actus: News
    let programme: Programme
}
private enum SectionTab: String, CaseIterable {
    case home = "Accueil", news = "Actualités", requests = "Demandes", more = "Plus"
    var icon: String { switch self { case .home: "house"; case .news: "newspaper"; case .requests: "folder"; case .more: "ellipsis" } }
}
struct PublicTabs: View {
    @State private var selected = SectionTab.home
    @State private var filter = "À la une"
    @State private var content: PublicContent?
    @State private var warning: String?
    @State private var loading = false
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @Namespace private var selection
    var body: some View {
        TabView(selection: $selected) {
            page("BININGA") {
                VStack(alignment: .leading, spacing: 4) {
                    Text("Ange Aimé Wilfrid BININGA")
                        .font(.subheadline.weight(.semibold))
                    Text("Député d’Ewo, République du Congo")
                        .font(.caption).foregroundStyle(cream.opacity(0.72))
                }
                Color.clear
                    .aspectRatio(16 / 9, contentMode: .fit)
                    .overlay {
                        GeometryReader { geometry in
                            Image("Ewo")
                                .resizable().scaledToFill()
                                .frame(width: geometry.size.width, height: geometry.size.height)
                                .clipped()
                        }
                    }
                    .overlay {
                        LinearGradient(
                            stops: [.init(color: .clear, location: 0.3),
                                    .init(color: .black.opacity(0.25), location: 0.55),
                                    .init(color: .black.opacity(0.9), location: 1)],
                            startPoint: .top, endPoint: .bottom
                        )
                    }
                    .overlay(alignment: .bottomLeading) {
                        Text("Ewo, au cœur de notre action")
                            .font(.system(.title2, design: .serif).weight(.semibold))
                            .tracking(-0.4)
                            .lineSpacing(1)
                            .fixedSize(horizontal: false, vertical: true)
                            .padding(20)
                    }
                    .clipShape(RoundedRectangle(cornerRadius: 24, style: .continuous))
                    .accessibilityElement(children: .combine)
                VStack(alignment: .leading, spacing: 8) {
                    Text("Servir Ewo avec écoute et responsabilité")
                        .font(.system(.headline, design: .serif).weight(.semibold))
                        .fixedSize(horizontal: false, vertical: true)
                    Text("À vos côtés, porter vos préoccupations au Parlement et contribuer au développement durable de notre localité.")
                        .font(.footnote).foregroundStyle(cream.opacity(0.78))
                        .fixedSize(horizontal: false, vertical: true)
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(16)
                .background(.white.opacity(0.06), in: RoundedRectangle(cornerRadius: 18))
                VStack(spacing: 10) {
                    action("Demander une audience", "calendar", .audience, true)
                    action("Suivre ma demande", "doc.text.magnifyingglass", .tracking(""))
                }
            }.tag(SectionTab.home)
            page("Actualités") {
                Picker("Rubrique",selection:$filter) { ForEach(["À la une","Terrain","Programme"],id:\.self){ Text($0) } }.pickerStyle(.segmented)
                if let warning { Text(warning).font(.footnote); Button("Actualiser") { Task { await refresh() } }.disabled(loading) }
                if let content {
                    if filter == "Programme" {
                        ForEach(Array((content.programme.axes ?? []).enumerated()),id:\.offset) { _, axis in
                            VStack(alignment:.leading,spacing:8) {
                                Text(axis.title).font(.headline)
                                if let text = axis.text { Text(text) }
                                ForEach(Array((axis.points ?? []).enumerated()),id:\.offset) { _, point in Text("• " + point) }
                            }.panel()
                        }
                    } else {
                        let articles = filter == "Terrain" ? content.actus.cards ?? [] : (content.actus.slides ?? []) + (content.actus.vedettes ?? [])
                        if articles.isEmpty { Text("Aucune publication dans cette rubrique.") }
                        ForEach(Array(articles.enumerated()),id:\.offset) { _, item in
                            NavigationLink {
                                ScrollView { VStack(alignment:.leading,spacing:12) {
                                    photo(item); Text(item.title).font(.system(.title,design:.serif).bold())
                                    if let date=item.date { Text(date).font(.caption) }
                                    Text(item.bodyText)
                                    if let raw=item.sourceUrl, let url=URL(string:raw), url.scheme=="https" { Link(item.source ?? "Lire la source",destination:url) }
                                }.padding() }.navigationTitle("Actualité").navigationBarTitleDisplayMode(.inline)
                            } label: { VStack(alignment:.leading,spacing:10) { photo(item); Text(item.title).font(.system(.headline,design:.serif)) }.panel() }.buttonStyle(.plain)
                        }
                    }
                } else if loading { ProgressView("Chargement des actualités") }
            }.tag(SectionTab.news)
            page("Mes démarches") {
                action("Demander une audience","calendar",.audience,true)
                action("Déposer une réclamation","bubble.left",.complaint)
                action("Suivre ma demande","folder",.tracking(""))
            }.tag(SectionTab.requests)
            page("Mon espace") {
                Text("Retrouvez votre dossier avec la référence reçue sur le site ou dans l’application.")
                action("Suivre ma demande","doc.text.magnifyingglass",.tracking(""),true)
                Link("Consulter le site BININGA",destination:site).panel()
            }.tag(SectionTab.more)
        }.tabViewStyle(.page(indexDisplayMode:.never))
        .safeAreaInset(edge:.bottom,spacing:0) {
            HStack(spacing:0) { ForEach(SectionTab.allCases,id:\.self) { tab in
                Button { withAnimation(reduceMotion ? nil : .easeInOut(duration:0.22)){selected=tab} } label: {
                    VStack(spacing: 4) {
                        Image(systemName: tab.icon).font(.system(size: 20, weight: .medium))
                        Text(tab.rawValue).font(.caption2.weight(.medium))
                    }
                        .frame(maxWidth:.infinity,minHeight:48)
                        .background { if selected==tab { Capsule().fill(wine).matchedGeometryEffect(id:"selected",in:selection) } }
                }.buttonStyle(.plain).contentShape(Rectangle())
                .accessibilityLabel(tab.rawValue)
                .accessibilityAddTraits(selected==tab ? .isSelected : [])
            }}.padding(5)
                .background(.ultraThinMaterial, in: Capsule())
                .overlay { Capsule().strokeBorder(cream.opacity(0.1), lineWidth: 0.5) }
                .padding(.horizontal, 20)
                .padding(.top, 8)
                .padding(.bottom, 8)
        }.foregroundStyle(cream)
        .background(charcoal.ignoresSafeArea())
        .toolbar(.hidden, for: .navigationBar)
        .task { await refresh() }
    }
    private func page<V:View>(_ title:String,@ViewBuilder _ contents:()->V)->some View {
        ScrollView { VStack(alignment:.leading,spacing:14) {
            Text(title)
                .font(.system(.title, design: .serif).weight(.semibold))
                .tracking(-0.5)
                .fixedSize(horizontal: false, vertical: true)
                .accessibilityAddTraits(.isHeader)
            RoundedRectangle(cornerRadius: 1)
                .fill(indicator).frame(width: 34, height: 3)
                .accessibilityHidden(true)
            contents()
        }.frame(maxWidth: 600, alignment: .leading)
            .padding(.horizontal, 20).padding(.top, 8).padding(.bottom, 24)
            .frame(maxWidth: .infinity)
        }
        .scrollIndicators(.hidden)
    }
    private func action(_ name:String,_ icon:String,_ route:Route,_ primary:Bool=false)->some View {
        NavigationLink(value:route) { HStack { Label(name,systemImage:icon); Spacer(); Image(systemName:"chevron.right") }
            .font(.body.weight(.semibold))
            .frame(minHeight: 24).padding(.horizontal, 16).padding(.vertical, 10)
            .background(primary ? wine : Color.white.opacity(0.06),in:RoundedRectangle(cornerRadius:14))
            .overlay { RoundedRectangle(cornerRadius: 14).strokeBorder(cream.opacity(primary ? 0.1 : 0.35), lineWidth: 0.5) } }.buttonStyle(.plain)
    }
    @ViewBuilder private func photo(_ item:Publication)->some View {
        if let raw=item.image,!raw.isEmpty, let url=URL(string:raw,relativeTo:site)?.absoluteURL, url.scheme=="https" {
            AsyncImage(url:url){ phase in
                if let image=phase.image {image.resizable().scaledToFit().clipShape(RoundedRectangle(cornerRadius:8))}
            }
        }
    }
    @MainActor private func refresh() async {
        guard !loading else{return}; loading=true;defer{loading=false}
        if content==nil,let file=Bundle.main.url(forResource:"PublicContent",withExtension:"json"),let data=try? Data(contentsOf:file) {
            content=try? JSONDecoder().decode(PublicContent.self,from:data)
        }
        do {
            let req=URLRequest(url:site.appendingPathComponent("api/load"),timeoutInterval:12)
            let (data,response)=try await URLSession.shared.data(for:req)
            guard let http=response as? HTTPURLResponse,http.statusCode==200 else{throw URLError(.badServerResponse)}
            content=try JSONDecoder().decode(PublicContent.self,from:data);warning=nil
        } catch { if !Task.isCancelled {warning=content==nil ? "Contenu indisponible." : "Version embarquée · Actualisation indisponible."} }
    }
}
private extension View {
    func panel()->some View { self.frame(maxWidth:.infinity,alignment:.leading).padding().background(Color.white.opacity(0.08),in:RoundedRectangle(cornerRadius:12)) }
}
