// UI text for the answer card in English, Sinhala and Tamil.
// The backend already translates the *content* (summary, explanation, recommendations);
// this file translates the fixed labels around it. Wording should be reviewed by native speakers.

export type Lang = 'en' | 'si' | 'ta'

export interface UiText {
  riskAssessment: string
  riskFactors: string
  detailedAnalysis: string
  recommendations: string
  evidenceSources: string
  confidence: string
  agents: string
  readAloud: string
  playing: string
  generating: string
  risk: Record<string, string>      // badge label per risk level
  priority: Record<string, string>  // label per recommendation priority
}

const UI: Record<Lang, UiText> = {
  en: {
    riskAssessment: 'Risk Assessment',
    riskFactors: 'Risk Factors:',
    detailedAnalysis: 'Detailed Analysis',
    recommendations: 'Recommendations',
    evidenceSources: 'Evidence Sources',
    confidence: 'Confidence',
    agents: 'agents',
    readAloud: 'Read aloud',
    playing: 'Playing...',
    generating: 'Generating...',
    risk: { low: 'Low Risk', moderate: 'Moderate Risk', high: 'High Risk', critical: 'Critical Risk', unknown: 'Unknown Risk' },
    priority: { immediate: 'immediate', 'short-term': 'short-term', 'long-term': 'long-term' },
  },
  si: {
    riskAssessment: 'අවදානම් තක්සේරුව',
    riskFactors: 'අවදානම් සාධක:',
    detailedAnalysis: 'සවිස්තරාත්මක විශ්ලේෂණය',
    recommendations: 'නිර්දේශ',
    evidenceSources: 'සාක්ෂි මූලාශ්‍ර',
    confidence: 'විශ්වාසනීයත්වය',
    agents: 'නියෝජිතයන්',
    readAloud: 'හඬ නගා කියවන්න',
    playing: 'වාදනය වෙමින්...',
    generating: 'සකසමින්...',
    risk: { low: 'අඩු අවදානම', moderate: 'මධ්‍යම අවදානම', high: 'ඉහළ අවදානම', critical: 'බරපතල අවදානම', unknown: 'නොදන්නා අවදානම' },
    priority: { immediate: 'ක්ෂණික', 'short-term': 'කෙටි කාලීන', 'long-term': 'දිගු කාලීන' },
  },
  ta: {
    riskAssessment: 'ஆபத்து மதிப்பீடு',
    riskFactors: 'ஆபத்து காரணிகள்:',
    detailedAnalysis: 'விரிவான பகுப்பாய்வு',
    recommendations: 'பரிந்துரைகள்',
    evidenceSources: 'சான்று மூலங்கள்',
    confidence: 'நம்பகத்தன்மை',
    agents: 'முகவர்கள்',
    readAloud: 'உரக்கப் படிக்க',
    playing: 'இயக்கப்படுகிறது...',
    generating: 'உருவாக்குகிறது...',
    risk: { low: 'குறைந்த ஆபத்து', moderate: 'மிதமான ஆபத்து', high: 'அதிக ஆபத்து', critical: 'தீவிர ஆபத்து', unknown: 'அறியப்படாத ஆபத்து' },
    priority: { immediate: 'உடனடி', 'short-term': 'குறுகிய காலம்', 'long-term': 'நீண்ட காலம்' },
  },
}

/** Labels for a response language code; falls back to English. */
export function uiText(language?: string): UiText {
  return UI[(language as Lang) in UI ? (language as Lang) : 'en']
}
