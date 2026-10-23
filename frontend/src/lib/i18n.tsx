import React, { createContext, useContext, useState } from 'react';

export type Language = 'EN' | 'HI';

const translations: Record<Language, Record<string, string>> = {
  EN: {
    // Brand & Header
    'brand.title': 'AICTE FDR VAULT',
    'brand.subtitle': 'SIH-2026 SOVEREIGN',
    'brand.custody': 'Institutional Custody',
    'brand.adapter': 'SIMULATED BANK ADAPTER (SIH-26265)',
    'brand.exportLedger': 'Export Ledger',
    'brand.eval': 'EVAL:',
    'brand.sim': 'SIM:',
    'brand.logout': 'Log Out',
    'brand.nodeLedger': 'NODE LEDGER SYNC',
    'brand.chainParity': 'CHAIN PARITY',
    'brand.protocol': 'AICTE SIH-26265 PROTOCOL',

    // Nav
    'nav.repository': 'Central Repository',
    'nav.intake': 'OCR Intake Studio',
    'nav.verification': 'Verification Matrix',
    'nav.maturity': 'Maturity Radar',
    'nav.release': 'Controlled Release',
    'nav.reports': 'Reports & Exports',
    'nav.audit': 'Hash Audit Ledger',

    // Common Actions & Form
    'action.search': 'Search by FDR number, institution or bank...',
    'action.filter': 'Filter Records',
    'action.submitFdr': 'Submit New FDR',
    'action.upload': 'Upload Document',
    'action.download': 'Download Document',
    'action.cancel': 'Cancel',
    'action.save': 'Save Changes',
    'action.confirm': 'Confirm Action',
    'action.viewDetails': 'View Details',
    'action.review': 'Review Application',
    'action.refresh': 'Refresh Data',

    // Statuses
    'status.active': 'Active',
    'status.submitted': 'Submitted',
    'status.renewal_due': 'Renewal Due',
    'status.matured': 'Matured',
    'status.renewed': 'Renewed',
    'status.released': 'Released',
    'status.verified': 'Verified',
    'status.pending': 'Pending',
    'status.discrepancy': 'Discrepancy',
    'status.rejected': 'Rejected',

    // Fields
    'field.fdrNumber': 'FDR Number',
    'field.bankName': 'Issuing Bank',
    'field.branch': 'Branch Name',
    'field.amount': 'Principal Amount',
    'field.issueDate': 'Issue Date',
    'field.maturityDate': 'Maturity Date',
    'field.roi': 'Interest Rate',
    'field.institution': 'Institution',
    'field.lien': 'Lien Clause',
    'field.actions': 'Actions',

    // Dashboard Telemetry
    'dash.totalFdrs': 'Total FDR Instruments',
    'dash.activeAmount': 'Total Active Collateral',
    'dash.expiring30': 'Expiring in 30 Days',
    'dash.flaggedDiscrepancies': 'Flagged Discrepancies',
    'dash.maturedUnreleased': 'Matured (Unreleased)',
    'dash.recentSubmissions': 'Recent Submissions & Events',
    'dash.priorityCases': 'Priority Cases Requiring Action',
    'dash.statusDistribution': 'Status Distribution',
    'dash.monthlyMaturity': '12-Month Maturity Forecast',
    'dash.bankConcentration': 'Bank Concentration',

    // Auth
    'auth.loginTitle': 'Sign In to Security Deposit Vault',
    'auth.email': 'Official Email Address',
    'auth.password': 'Password',
    'auth.signInButton': 'Authenticate & Enter Vault',
    'auth.demoJudges': 'Evaluator Demo Access',
    'auth.changePassword': 'Change Password',
  },
  HI: {
    // Brand & Header
    'brand.title': 'एआईसीटीई एफडीआर वॉल्ट',
    'brand.subtitle': 'एसआईएच-2026 संप्रभु पोर्टल',
    'brand.custody': 'संस्थागत अभिरक्षा',
    'brand.adapter': 'सिम्युलेटेड बैंक एडेप्टर (SIH-26265)',
    'brand.exportLedger': 'लेज़र निर्यात',
    'brand.eval': 'मूल्यांकन:',
    'brand.sim': 'सिम्युलेशन:',
    'brand.logout': 'लॉग आउट',
    'brand.nodeLedger': 'नोड लेज़र सिंक',
    'brand.chainParity': 'श्रृंखला समता',
    'brand.protocol': 'एआईसीटीई एसआईएच-26265 प्रोटोकॉल',

    // Nav
    'nav.repository': 'केंद्रीय रिपोजिटरी',
    'nav.intake': 'ओसीआर इनटेक स्टूडियो',
    'nav.verification': 'सत्यापन मैट्रिक्स',
    'nav.maturity': 'परिपक्वता रडार',
    'nav.release': 'नियंत्रित विमोचन',
    'nav.reports': 'रिपोर्ट और निर्यात',
    'nav.audit': 'हैश ऑडिट लेज़र',

    // Common Actions & Form
    'action.search': 'एफडीआर नंबर, संस्थान या बैंक द्वारा खोजें...',
    'action.filter': 'फ़िल्टर करें',
    'action.submitFdr': 'नया एफडीआर जमा करें',
    'action.upload': 'दस्तावेज़ अपलोड करें',
    'action.download': 'दस्तावेज़ डाउनलोड करें',
    'action.cancel': 'रद्द करें',
    'action.save': 'परिवर्तन सहेजें',
    'action.confirm': 'पुष्टि करें',
    'action.viewDetails': 'विवरण देखें',
    'action.review': 'समीक्षा करें',
    'action.refresh': 'रिफ्रेश करें',

    // Statuses
    'status.active': 'सक्रिय',
    'status.submitted': 'प्रस्तुत',
    'status.renewal_due': 'नवीकरण देय',
    'status.matured': 'परिपक्व',
    'status.renewed': 'नवीनीकृत',
    'status.released': 'विमोचित',
    'status.verified': 'सत्यापित',
    'status.pending': 'लंबित',
    'status.discrepancy': 'विसंगति',
    'status.rejected': 'अस्वीकृत',

    // Fields
    'field.fdrNumber': 'एफडीआर संख्या',
    'field.bankName': 'जारीकर्ता बैंक',
    'field.branch': 'शाखा का नाम',
    'field.amount': 'मूलधन राशि',
    'field.issueDate': 'जारी करने की तिथि',
    'field.maturityDate': 'परिपक्वता तिथि',
    'field.roi': 'ब्याज दर',
    'field.institution': 'संस्थान',
    'field.lien': 'ग्रहणाधिकार (Lien)',
    'field.actions': 'कार्रवाई',

    // Dashboard Telemetry
    'dash.totalFdrs': 'कुल एफडीआर साधन',
    'dash.activeAmount': 'कुल सक्रिय संपार्श्विक',
    'dash.expiring30': '30 दिनों में परिपक्व',
    'dash.flaggedDiscrepancies': 'चिह्नित विसंगतियां',
    'dash.maturedUnreleased': 'परिपक्व (अविमोचित)',
    'dash.recentSubmissions': 'हालिया प्रस्तुतियां और घटनाएं',
    'dash.priorityCases': 'त्वरित समीक्षा हेतु प्राथमिकता मामले',
    'dash.statusDistribution': 'स्थिति वितरण',
    'dash.monthlyMaturity': '12-माह परिपक्वता पूर्वानुमान',
    'dash.bankConcentration': 'बैंक एकाग्रता',

    // Auth
    'auth.loginTitle': 'सुरक्षा जमा वॉल्ट में प्रवेश करें',
    'auth.email': 'आधिकारिक ईमेल पता',
    'auth.password': 'पासवर्ड',
    'auth.signInButton': 'प्रमाणित करें और प्रवेश करें',
    'auth.demoJudges': 'मूल्यांकनकर्ता डेमो लॉगिन',
    'auth.changePassword': 'पासवर्ड बदलें',
  },
};

interface I18nContextType {
  lang: Language;
  language: Language;
  setLang: (lang: Language) => void;
  toggleLang: () => void;
  toggleLanguage: () => void;
  t: (key: string, fallback?: string) => string;
}

const I18nContext = createContext<I18nContextType | undefined>(undefined);

export const I18nProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [lang, setLangState] = useState<Language>(() => {
    const saved = localStorage.getItem('fdr_portal_lang');
    return saved === 'HI' ? 'HI' : 'EN';
  });

  const setLang = (newLang: Language) => {
    setLangState(newLang);
    localStorage.setItem('fdr_portal_lang', newLang);
  };

  const toggleLang = () => {
    setLang(lang === 'EN' ? 'HI' : 'EN');
  };

  const t = (key: string, fallback?: string): string => {
    return translations[lang]?.[key] || translations['EN']?.[key] || fallback || key;
  };

  return (
    <I18nContext.Provider
      value={{
        lang,
        language: lang,
        setLang,
        toggleLang,
        toggleLanguage: toggleLang,
        t,
      }}
    >
      {children}
    </I18nContext.Provider>
  );
};

export const useI18n = () => {
  const context = useContext(I18nContext);
  if (!context) {
    throw new Error('useI18n must be used within an I18nProvider');
  }
  return context;
};
