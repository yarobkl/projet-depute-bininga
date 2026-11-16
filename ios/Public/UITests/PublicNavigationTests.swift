import XCTest

final class PublicNavigationTests: XCTestCase {
    private func reveal(_ element: XCUIElement, in app: XCUIApplication) {
        for _ in 0..<7 {
            if element.exists && element.isHittable { return }
            app.swipeUp()
        }
        XCTAssertTrue(element.exists && element.isHittable, app.debugDescription)
    }
    private func capture(_ name: String) {
        let attachment = XCTAttachment(screenshot: XCUIApplication().screenshot())
        attachment.name = name; attachment.lifetime = .keepAlways; add(attachment)
    }
    func testPublicRoutes() throws {
        let app = XCUIApplication()
        continueAfterFailure = false
        app.launch()
        let springboard = XCUIApplication(bundleIdentifier: "com.apple.springboard")
        if springboard.alerts.firstMatch.waitForExistence(timeout: 4) {
            let allow = springboard.buttons["Allow"]
            if allow.exists { allow.tap() }
            else if springboard.buttons["Autoriser"].exists { springboard.buttons["Autoriser"].tap() }
        }
        XCTAssertTrue(app.staticTexts["Ange Aimé Wilfrid BININGA"].firstMatch.waitForExistence(timeout: 10))
        capture("Accueil — portrait et identité")
        let audience = app.buttons["Demander une audience"].firstMatch
        reveal(audience, in: app); audience.tap()
        XCTAssertTrue(app.textFields["Prénom"].waitForExistence(timeout: 5))
        XCTAssertFalse(app.buttons["Envoyer ma demande"].isEnabled)
        app.navigationBars.buttons.firstMatch.tap()

        let programme = app.buttons["Lire le programme"].firstMatch
        reveal(programme, in: app); programme.tap()
        XCTAssertTrue(app.buttons["Sommaire"].firstMatch.waitForExistence(timeout: 5))
        capture("Programme — lecture native")
        app.navigationBars.buttons.firstMatch.tap()
        app.tabBars.buttons["Actualités"].tap()
        app.segmentedControls.buttons["Programme"].tap()
        app.buttons["programme-reader-link"].tap()
        XCTAssertTrue(app.buttons["Sommaire"].firstMatch.waitForExistence(timeout: 5))
        app.navigationBars.buttons.firstMatch.tap()

        app.tabBars.buttons["Demandes"].tap()
        app.buttons["Déposer une réclamation"].firstMatch.tap()
        XCTAssertTrue(app.textFields["Prénom"].waitForExistence(timeout: 5))
        app.navigationBars.buttons.firstMatch.tap()
        let tracking = app.buttons["Suivre ma demande"].firstMatch
        reveal(tracking, in: app); tracking.tap()
        XCTAssertTrue(app.textFields["Numéro du dossier"].waitForExistence(timeout: 5))
        XCTAssertFalse(app.buttons["Consulter le suivi"].isEnabled)
        app.navigationBars.buttons.firstMatch.tap()

        app.tabBars.buttons["Découvrir"].tap()
        XCTAssertFalse(app.buttons["Suivre ma demande"].exists)
        XCTAssertFalse(app.buttons["Demander une audience"].exists)
        capture("Découvrir — sans doublon de démarches")
        app.buttons["Son parcours"].tap()
        XCTAssertTrue(app.navigationBars["Son parcours"].waitForExistence(timeout: 5))
    }
}
