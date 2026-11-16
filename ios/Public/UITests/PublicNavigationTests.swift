import XCTest

final class PublicNavigationTests: XCTestCase {
    func testPublicRoutes() throws {
        let app = XCUIApplication()
        continueAfterFailure = false
        app.launch()
        let audience = app.buttons["Demander une audience"].firstMatch
        XCTAssertTrue(audience.waitForExistence(timeout: 10))
        audience.tap()
        XCTAssertTrue(app.textFields["Prénom"].waitForExistence(timeout: 5))
        XCTAssertFalse(app.buttons["Envoyer ma demande"].isEnabled)
        app.navigationBars.buttons.firstMatch.tap()

        app.buttons["Actualités"].firstMatch.tap()
        app.buttons["Programme"].firstMatch.tap()
        XCTAssertTrue(app.staticTexts["Justice accessible"].waitForExistence(timeout: 10), app.debugDescription)
        app.buttons["Demandes"].firstMatch.tap()
        app.buttons["Déposer une réclamation"].firstMatch.tap()
        XCTAssertTrue(app.textFields["Prénom"].waitForExistence(timeout: 5))
        app.navigationBars.buttons.firstMatch.tap()

        app.buttons["Plus"].firstMatch.tap()
        app.buttons["Suivre ma demande"].firstMatch.tap()
        XCTAssertTrue(app.textFields["Numéro du dossier"].waitForExistence(timeout: 5))
        XCTAssertFalse(app.buttons["Consulter le suivi"].isEnabled)
    }
}
