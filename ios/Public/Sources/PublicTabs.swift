import SwiftUI

private let site = URL(string: "https://projet-depute-bininga.vercel.app")!
private let cream = Color(red: 0.97, green: 0.92, blue: 0.83)
private let wine = Color(red: 0.57, green: 0.035, blue: 0.16)

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
                GeometryReader { geometry in
                    Image("Ewo")
                        .resizable().scaledToFill()
                        .frame(width: geometry.size.width, height: geometry.size.height)
                        .clipped()
                        .overlay {
                            LinearGradient(colors: [.clear, .black.opacity(0.85)], startPoint: .center, endPoint: .bottom)
                        }
                        .overlay(alignment: .bottomLeading) {
                            Text("Ewo, au cœur de notre action")
                                .font(.system(.title, design: .serif).weight(.semibold))
                                .fixedSize(horizontal: false, vertical: true)
                                .padding(20)
                        }
                }
                .frame(height: 250)
                .clipShape(RoundedRectangle(cornerRadius: 22, style: .continuous))
                .accessibilityLabel("Ewo, au cœur de notre action")
                VStack(alignment: .leading, spacing: 8) {
                    Text("Servir Ewo avec écoute et responsabilité")
                        .font(.system(.title3, design: .serif).weight(.semibold))
                        .fixedSize(horizontal: false, vertical: true)
                    Text("À vos côtés, porter vos préoccupations au Parlement et contribuer au développement durable de notre localité.")
                        .font(.subheadline).foregroundStyle(cream.opacity(0.78))
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
                                ScrollView { VStack(alignment:.leading,spacing:14) {
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
                Button { withAnimation(.easeInOut(duration:0.22)){selected=tab} } label: {
                    VStack(spacing: 4) {
                        Image(systemName: tab.icon).font(.system(size: 20, weight: .medium))
                        Text(tab.rawValue).font(.caption2.weight(.medium))
                    }
                        .frame(maxWidth:.infinity,minHeight:52)
                        .background { if selected==tab { Capsule().fill(wine).matchedGeometryEffect(id:"selected",in:selection) } }
                }.buttonStyle(.plain).accessibilityAddTraits(selected==tab ? .isSelected : [])
            }}.padding(5).background(.ultraThinMaterial,in:Capsule()).padding(.horizontal,12)
        }.foregroundStyle(cream)
        .toolbar(.hidden, for: .navigationBar)
        .task { await refresh() }
    }
    private func page<V:View>(_ title:String,@ViewBuilder _ contents:()->V)->some View {
        ScrollView { VStack(alignment:.leading,spacing:14) {
            Text(title).font(.system(.largeTitle,design:.serif).weight(.semibold)).accessibilityAddTraits(.isHeader)
            contents()
        }.frame(maxWidth: 600, alignment: .leading)
            .padding(.horizontal, 20).padding(.top, 12).padding(.bottom, 24)
            .frame(maxWidth: .infinity)
        }
        .scrollIndicators(.hidden)
    }
    private func action(_ name:String,_ icon:String,_ route:Route,_ primary:Bool=false)->some View {
        NavigationLink(value:route) { HStack { Label(name,systemImage:icon); Spacer(); Image(systemName:"chevron.right") }
            .font(.body.weight(.semibold))
            .frame(minHeight: 24).padding(.horizontal, 16).padding(.vertical, 14)
            .background(primary ? wine : Color.white.opacity(0.09),in:RoundedRectangle(cornerRadius:12)) }.buttonStyle(.plain)
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
