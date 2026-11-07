import Foundation
import UIKit
import Display
import AsyncDisplayKit
import TelegramCore
import SSignalKit
import SwiftSignalKit
import TelegramPresentationData
import LegacyComponents
import SolidRoundedButtonNode
import RMIntro

public final class AuthorizationSequenceSplashController: ViewController {
    private var controllerNode: AuthorizationSequenceSplashControllerNode {
        return self.displayNode as! AuthorizationSequenceSplashControllerNode
    }
    
    private let accountManager: AccountManager<TelegramAccountManagerTypes>
    private let account: UnauthorizedAccount
    private let theme: PresentationTheme
    
    private let controller: RMIntroViewController
    
    private var validLayout: ContainerViewLayout?
    
    var nextPressed: ((PresentationStrings?) -> Void)?
    
    private let suggestedLocalization = Promise<SuggestedLocalizationInfo?>()
    private let activateLocalizationDisposable = MetaDisposable()
    
    private let startButton: SolidRoundedButtonNode
    
    init(accountManager: AccountManager<TelegramAccountManagerTypes>, account: UnauthorizedAccount, theme: PresentationTheme, existingLocalizationCode: String?) {
        self.accountManager = accountManager
        self.account = account
        self.theme = theme
        
        self.suggestedLocalization.set(.single(nil)
        |> then(TelegramEngineUnauthorized(account: self.account).localization.currentlySuggestedLocalization(extractKeys: ["Login.ContinueWithLocalization"])))
        let suggestedLocalization = self.suggestedLocalization
        
        let localizationSignal = SSignal(generator: { subscriber in
            let disposable = suggestedLocalization.get().start(next: { localization in
                guard let localization = localization else {
                    return
                }
                
                var continueWithLanguageString: String = "Continue"
                for entry in localization.extractedEntries {
                    switch entry {
                        case let .string(key, value):
                            if key == "Login.ContinueWithLocalization" {
                                continueWithLanguageString = value
                            }
                        default:
                            break
                    }
                }
                
                if let available = localization.availableLocalizations.first, available.languageCode != "en" {
                    let value = TGSuggestedLocalization(info: TGAvailableLocalization(title: available.title, localizedTitle: available.localizedTitle, code: available.languageCode), continueWithLanguageString: continueWithLanguageString, chooseLanguageString: "Choose Language", chooseLanguageOtherString: "Choose Language", englishLanguageNameString: "English")
                    subscriber.putNext(value)
                }
            }, completed: {
                subscriber.putCompletion()
            })
            
            return SBlockDisposable(block: {
                disposable.dispose()
            })
        })
        
        let initialLocalizationCode = InitialLocalization.code(for: Locale.preferredLanguages, existingLanguageCode: existingLocalizationCode)

        self.controller = RMIntroViewController(backgroundColor: theme.list.plainBackgroundColor, primaryColor: theme.list.itemPrimaryTextColor, buttonColor: theme.intro.startButtonColor, accentColor: theme.list.itemAccentColor, regularDotColor: theme.intro.dotColor, highlightedDotColor: theme.list.itemAccentColor, languageCode: InitialLocalization.introResourceCode(for: initialLocalizationCode), suggestedLocalizationSignal: localizationSignal)
        
        self.startButton = SolidRoundedButtonNode(title: InitialLocalization.startButtonTitle(for: initialLocalizationCode), theme: SolidRoundedButtonTheme(theme: theme), glass: false, height: 50.0, cornerRadius: 50.0 * 0.5, isShimmering: true)
        self.startButton.accessibilityIdentifier = "Auth.Welcome.StartButton"

        super.init(navigationBarPresentationData: nil)
        
        self._hasGlassStyle = true
        
        self.supportedOrientations = ViewControllerSupportedOrientations(regularSize: .all, compactSize: .portrait)
        
        self.statusBar.statusBarStyle = theme.intro.statusBarStyle.style
        
        self.controller.startMessaging = { [weak self] in
            self?.activateLocalization(initialLocalizationCode, preserveExistingLanguage: true)
        }
        self.controller.startMessagingInAlternativeLanguage = { [weak self] code in
            if let code = code {
                self?.activateLocalization(code)
            }
        }
        
        self.startButton.pressed = { [weak self] in
            self?.activateLocalization(initialLocalizationCode, preserveExistingLanguage: true)
        }
        
        self.controller.createStartButton = { [weak self] width in
            let _ = self?.startButton.updateLayout(width: width, transition: .immediate)
            return self?.startButton.view
        }
    }
    
    required init(coder aDecoder: NSCoder) {
        fatalError("init(coder:) has not been implemented")
    }
    
    deinit {
        self.activateLocalizationDisposable.dispose()
    }
    
    public override func loadDisplayNode() {
        self.displayNode = AuthorizationSequenceSplashControllerNode(theme: self.theme)
        self.displayNodeDidLoad()
    }
    
    func animateIn() {
        self.controller.animateIn()
    }
    
    var buttonFrame: CGRect {
        return self.startButton.frame
    }
    
    var buttonTitle: String {
        return self.startButton.title ?? ""
    }
    
    var animationSnapshot: UIView? {
        return self.controller.createAnimationSnapshot()
    }
    
    var textSnaphot: UIView? {
        return self.controller.createTextSnapshot()
    }
    
    private func addControllerIfNeeded() {
        if !self.controller.isViewLoaded || self.controller.view.superview == nil {
            self.displayNode.view.addSubview(self.controller.view)
            if let layout = self.validLayout {
                controller.view.frame = CGRect(origin: CGPoint(), size: layout.size)
            }
            self.controller.viewDidAppear(false)
        }
    }
    
    public override func viewWillAppear(_ animated: Bool) {
        super.viewWillAppear(animated)
        self.addControllerIfNeeded()
        self.controller.viewWillAppear(false)
    }
    
    public override func viewDidAppear(_ animated: Bool) {
        super.viewDidAppear(animated)
        
        controller.viewDidAppear(animated)
    }
    
    public override func viewWillDisappear(_ animated: Bool) {
        super.viewWillDisappear(animated)
        
        controller.viewWillDisappear(animated)
    }
    
    public override func viewDidDisappear(_ animated: Bool) {
        super.viewDidDisappear(animated)
        
        controller.viewDidDisappear(animated)
    }
    
    public override func containerLayoutUpdated(_ layout: ContainerViewLayout, transition: ContainedViewLayoutTransition) {
        super.containerLayoutUpdated(layout, transition: transition)
        
        self.validLayout = layout
        let controllerFrame = CGRect(origin: CGPoint(), size: layout.size)
        self.controller.defaultFrame = controllerFrame
        
        self.controllerNode.containerLayoutUpdated(layout, navigationBarHeight: 0.0, transition: transition)
        
        self.addControllerIfNeeded()
        if case .immediate = transition {
            self.controller.view.frame = controllerFrame
        } else {
            UIView.animate(withDuration: 0.3, animations: {
                self.controller.view.frame = controllerFrame
            })
        }
    }
    
    private func activateLocalization(_ requestedCode: String, preserveExistingLanguage: Bool = false) {
        let currentCode = self.accountManager.transaction { transaction -> String? in
            if let current = transaction.getSharedData(SharedDataKeys.localizationSettings)?.get(LocalizationSettings.self) {
                return current.primaryComponent.languageCode
            } else {
                return nil
            }
        }
        let _ = (currentCode
        |> take(1)
        |> deliverOnMainQueue).start(next: { [weak self] currentCode in
            guard let strongSelf = self else {
                return
            }

            let code = preserveExistingLanguage ? InitialLocalization.code(for: Locale.preferredLanguages, existingLanguageCode: currentCode) : requestedCode

            if InitialLocalization.shouldUseBundledStrings(languageCode: code, existingLanguageCode: currentCode) {
                strongSelf.pressNext(strings: defaultPresentationStrings)
                return
            }

            let suggestedCode = strongSelf.suggestedLocalization.get()
            |> map { localization -> String? in
                return localization?.availableLocalizations.first?.languageCode
            }
            let _ = (suggestedCode
            |> take(1)
            |> deliverOnMainQueue).start(next: { [weak self] suggestedCode in
                self?.applyLocalization(code, currentCode: currentCode, suggestedCode: suggestedCode)
            })
        })
    }

    private func applyLocalization(_ code: String, currentCode: String?, suggestedCode: String?) {
        if let suggestedCode = suggestedCode {
            _ = TelegramEngineUnauthorized(account: self.account).localization.markSuggestedLocalizationAsSeenInteractively(languageCode: suggestedCode).start()
        }

        if currentCode == code {
            self.pressNext(strings: nil)
            return
        }

        self.controller.isEnabled = false
        self.startButton.alpha = 0.6
        let accountManager = self.accountManager

        self.activateLocalizationDisposable.set(TelegramEngineUnauthorized(account: self.account).localization.downloadAndApplyLocalization(accountManager: accountManager, languageCode: code).start(error: { [weak self] _ in
            self?.controller.isEnabled = true
            self?.startButton.alpha = 1.0
            self?.pressNext(strings: nil)
        }, completed: { [weak self] in
            let _ = (accountManager.transaction { transaction -> PresentationStrings? in
                let localizationSettings: LocalizationSettings?
                if let current = transaction.getSharedData(SharedDataKeys.localizationSettings)?.get(LocalizationSettings.self) {
                    localizationSettings = current
                } else {
                    localizationSettings = nil
                }
                let stringsValue: PresentationStrings
                if let localizationSettings = localizationSettings {
                    stringsValue = PresentationStrings(primaryComponent: PresentationStrings.Component(languageCode: localizationSettings.primaryComponent.languageCode, localizedName: localizationSettings.primaryComponent.localizedName, pluralizationRulesCode: localizationSettings.primaryComponent.customPluralizationCode, dict: dictFromLocalization(localizationSettings.primaryComponent.localization)), secondaryComponent: localizationSettings.secondaryComponent.flatMap({ PresentationStrings.Component(languageCode: $0.languageCode, localizedName: $0.localizedName, pluralizationRulesCode: $0.customPluralizationCode, dict: dictFromLocalization($0.localization)) }), groupingSeparator: "")
                } else {
                    stringsValue = defaultPresentationStrings
                }
                return stringsValue
            }
            |> deliverOnMainQueue).start(next: { [weak self] strings in
                self?.controller.isEnabled = true
                self?.startButton.alpha = 1.0
                self?.pressNext(strings: strings)
            })
        }))
    }
    
    private func pressNext(strings: PresentationStrings?) {
        if let navigationController = self.navigationController, navigationController.viewControllers.last === self {
            self.nextPressed?(strings)
        }
    }
}
