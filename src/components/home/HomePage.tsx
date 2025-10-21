import React from 'react';
import { Navbar } from '../layout/Navbar';
import { Clock, CheckCircle, BarChart3, MessageSquare } from 'lucide-react';
import { useLanguage } from '../i18n/LanguageContext';
import { ImageWithFallback } from '../figma/ImageWithFallback';

export function HomePage() {
  const { t, language } = useLanguage();

  return (
    <div className="min-h-screen bg-white">
      <Navbar />
      
      {/* Hero Section - Enhanced */}
      <section className="bg-gradient-to-br from-blue-50 via-indigo-50 to-purple-50 py-16 sm:py-24">
        <div className="max-w-7xl mx-auto px-6">
          <div className="grid lg:grid-cols-2 gap-12 items-center">
            <div className="space-y-8">
              {/* Title - Larger and More Prominent */}
              <h1 className="text-4xl sm:text-5xl lg:text-6xl font-extrabold text-gray-900 leading-tight">
                {language === 'hi' ? 'सहायक एआई' : 'Sahayak AI'}
              </h1>
              
              {/* Description - Improved Spacing and Readability */}
              <div className="space-y-4 text-lg text-gray-700 leading-relaxed">
                <p>
                  {language === 'hi' 
                    ? 'आपका व्यक्तिगत सीखने का साथी - होमवर्क में मदद, व्यक्तिगत पाठ, शिक्षक-सत्यापित उत्तर और वास्तविक समय की प्रदर्शन ट्रैकिंग।' 
                    : 'Your personal learning companion - homework help, personalized lessons, teacher-verified answers, and real-time performance tracking.'
                  }
                </p>
                <p className="font-medium">
                  {language === 'hi' 
                    ? '4 भारतीय भाषाओं में समर्थन के साथ - हिंदी, अंग्रेजी, तमिल और मराठी।' 
                    : 'With support for 4 Indian languages - Hindi, English, Tamil, and Marathi.'
                  }
                </p>
              </div>
              
              {/* Buttons - Enhanced Styling */}
              <div className="flex flex-col sm:flex-row gap-4 pt-4">
                <button 
                  onClick={() => window.location.href = '/register'} 
                 className="px-8 py-4 border-2 border-blue-600 text-blue-600 hover:bg-blue-50 font-bold rounded-xl transition-all duration-200 transform hover:-translate-y-0.5"
                >
                  {language === 'hi' ? 'अभी शुरू करें' : 'Start Learning Now'}
                </button>
                <button 
                  onClick={() => window.location.href = '/about'} 
                  className="px-8 py-4 border-2 border-blue-600 text-blue-600 hover:bg-blue-50 font-bold rounded-xl transition-all duration-200 transform hover:-translate-y-0.5"
                >
                  {language === 'hi' ? 'अधिक जानकारी' : 'Know More'}
                </button>
              </div>
            </div>
            
            {/* Image - Enhanced Presentation */}
            <div className="rounded-2xl overflow-hidden shadow-2xl border border-gray-200">
              <ImageWithFallback 
                src={require('../../assets/SahayakHome.png')}
                alt={language === 'hi' ? 'सहायक एआई कक्षा सहायक' : 'Sahayak AI classroom assistant'} 
                className="w-full h-full object-cover"
              />
            </div>
          </div>
        </div>
      </section>

      {/* Features Section - Enhanced */}
      <section className="bg-white py-20 border-b border-gray-100">
        <div className="max-w-7xl mx-auto px-6">
          <h2 className="text-3xl sm:text-4xl font-extrabold text-gray-900 mb-16 text-center">
            {language === 'hi' ? 'मुख्य सुविधाएँ' : 'Core Features'}
          </h2>
          
          <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-8">
            {[
              {
                icon: Clock,
                title: language === 'hi' ? 'स्वायत्त सामग्री अनुसूची' : 'Autonomous Content Scheduling',
                description: language === 'hi' 
                  ? 'एक बार सामग्री अपलोड करें। एआई स्वायत्त रूप से SEO-अनुकूलित YouTube वीडियो सिफारिशों के साथ पाठों की अनुसूची बनाता है।' 
                  : 'Upload material once. AI autonomously schedules lessons with SEO-optimized YouTube video recommendations.'
              },
              {
                icon: CheckCircle,
                title: language === 'hi' ? 'शिक्षक-नियंत्रित एआई ग्रेडिंग' : 'Teacher-Controlled AI Grading',
                description: language === 'hi' 
                  ? 'छात्र Google फॉर्म या Word के माध्यम से असाइनमेंट जमा करते हैं। शिक्षक मूल्यांकन योजनाएँ और मॉडल उत्तर परिभाषित करते हैं।' 
                  : 'Students submit assignments via Google Forms or Word. Teachers define evaluation schemas and model answers.'
              },
              {
                icon: MessageSquare,
                title: language === 'hi' ? '24/7 बुद्धिमान संदेह समाधानकर्ता' : '24/7 Intelligent Doubt Solver',
                description: language === 'hi' 
                  ? 'छात्र कभी भी प्रश्न पूछ सकते हैं। AWS Bedrock तुरंत उत्तर प्रदान करता है। शिक्षक प्रतिक्रियाओं की समीक्षा करते हैं और शिक्षण गुणवत्ता सुनिश्चित करते हैं।' 
                  : 'Students ask questions anytime. AWS Bedrock provides instant answers. Teachers review and approve responses before delivery, ensuring educational quality.'
              },
              {
                icon: BarChart3,
                title: language === 'hi' ? 'वास्तविक समय प्रदर्शन विश्लेषण' : 'Real-Time Performance Analytics',
                description: language === 'hi' 
                  ? 'बुद्धिमान डैशबोर्ड के साथ छात्र प्रगति ट्रैक करें। सीखने के पैटर्न की पहचान करें और व्यक्तिगत शिक्षण के लिए डेटा-संचालित निर्णय लें।' 
                  : 'Track student progress with intelligent dashboards. Identify learning patterns, celebrate top performers, and make data-driven decisions for personalized teaching.'
              }
            ].map((feature, idx) => {
              const Icon = feature.icon;
              return (
                <div 
                  key={idx} 
                  className="bg-white border border-gray-200 rounded-xl p-6 hover:border-blue-600 hover:shadow-xl transition-all duration-300 cursor-pointer group"
                >
                  <div className="w-14 h-14 bg-gradient-to-br from-blue-500 to-indigo-600 rounded-xl flex items-center justify-center mb-6 group-hover:scale-110 transition-transform">
                    <Icon className="h-7 w-7 text-white" />
                  </div>
                  <h3 className="text-xl font-bold text-gray-900 mb-4 group-hover:text-blue-600 transition-colors">
                    {feature.title}
                  </h3>
                  <p className="text-gray-700 leading-relaxed text-sm">
                    {feature.description}
                  </p>
                </div>
              );
            })}
          </div>
        </div>
      </section>

      {/* Why It Matters Section - Enhanced */}
      <section className="bg-white py-20 border-b border-gray-100">
        <div className="max-w-7xl mx-auto px-6">
          <div className="grid lg:grid-cols-2 gap-16">
            <div>
              <h2 className="text-3xl sm:text-4xl font-extrabold text-gray-900 mb-8">
                {language === 'hi' ? 'क्या बेहतर होता है' : 'What Gets Better'}
              </h2>
              <div className="space-y-6">
                {language === 'hi' 
                  ? [
                      'दोहराव वाले ग्रेडिंग कार्यों पर कम समय',
                      'अर्थपूर्ण छात्र अंतःक्रिया के लिए अधिक समय',
                      'छात्रों के सीखने के तरीके के बारे में बेहतर अंतर्दृष्टि',
                      'थकान के बिना सुसंगत प्रतिक्रिया',
                      'हर छात्र के लिए व्यक्तिगत शिक्षा',
                      'कई भाषाओं में समर्थन'
                    ]
                  : [
                      'Less time on repetitive grading tasks',
                      'More time for meaningful student interaction',
                      'Better insights into how students learn',
                      'Consistent feedback without burnout',
                      'Personalized learning for every student',
                      'Support in multiple languages'
                    ]
                .map((item, idx) => (
                  <div key={idx} className="flex gap-4 items-start">
                    <div className="w-6 h-6 rounded-full bg-blue-100 flex items-center justify-center flex-shrink-0 mt-0.5">
                      <span className="text-blue-600 text-sm font-bold">✓</span>
                    </div>
                    <p className="text-lg text-gray-700 leading-relaxed">{item}</p>
                  </div>
                ))}
              </div>
            </div>
            
            <div>
              <h2 className="text-3xl sm:text-4xl font-extrabold text-gray-900 mb-8">
                {language === 'hi' ? 'हमारी योजना' : 'Our Plan'}
              </h2>
              <div className="space-y-6">
                <div className="bg-gradient-to-br from-green-50 to-green-100 border-2 border-green-500 rounded-xl p-6 hover:shadow-lg transition-all duration-300">
                  <p className="text-sm text-green-700 font-semibold mb-3">
                    {language === 'hi' ? 'अभी' : 'Right Now'}
                  </p>
                  <p className="font-bold text-gray-900 mb-4">
                    {language === 'hi' ? 'हिंदी और अंग्रेजी' : 'Hindi & English'}
                  </p>
                  <ul className="space-y-2 text-sm text-gray-700">
                    <li className="flex gap-2"><span className="text-green-600">•</span> {language === 'hi' ? 'कक्षा 6-8 कवरेज' : 'Grades 6-8 coverage'}</li>
                    <li className="flex gap-2"><span className="text-green-600">•</span> {language === 'hi' ? 'मुख्य सुविधाएँ पूरी तरह से निर्मित और परीक्षण की गईं' : 'Core features fully built and tested'}</li>
                    <li className="flex gap-2"><span className="text-green-600">•</span> {language === 'hi' ? 'बहुभाषी ज्ञान आधार संरचना' : 'Multilingual knowledge base foundation'}</li>
                  </ul>
                </div>
                
                <div className="bg-gradient-to-br from-blue-50 to-blue-100 border-2 border-blue-500 rounded-xl p-6 hover:shadow-lg transition-all duration-300">
                  <p className="text-sm text-blue-700 font-semibold mb-3">
                    {language === 'hi' ? 'अगला चरण' : 'Next 3 Months'}
                  </p>
                  <p className="font-bold text-gray-900 mb-4">
                    {language === 'hi' ? 'तमिल और मराठी' : 'Tamil & Marathi'}
                  </p>
                  <ul className="space-y-2 text-sm text-gray-700">
                    <li className="flex gap-2"><span className="text-blue-600">•</span> {language === 'hi' ? 'क्षेत्रीय पाठ्यक्रम संरेखण' : 'Regional curriculum alignment'}</li>
                    <li className="flex gap-2"><span className="text-blue-600">•</span> {language === 'hi' ? 'हस्तलिखित असाइनमेंट मूल्यांकन' : 'Handwritten assignments evaluation'}</li>
                    <li className="flex gap-2"><span className="text-blue-600">•</span> {language === 'hi' ? 'टेक्स्ट-टू-स्पीच सक्षमता' : 'Text-to-speech enablement'}</li>
                  </ul>
                </div>
                
                <div className="bg-gradient-to-br from-purple-50 to-purple-100 border-2 border-purple-500 rounded-xl p-6 hover:shadow-lg transition-all duration-300">
                  <p className="text-sm text-purple-700 font-semibold mb-3">
                    {language === 'hi' ? 'भविष्य' : 'Future'}
                  </p>
                  <p className="font-bold text-gray-900 mb-4">
                    {language === 'hi' ? 'कक्षा 1-12, सभी भारतीय भाषाएँ' : 'Grades 1-12, All Indian Languages'}
                  </p>
                  <ul className="space-y-2 text-sm text-gray-700">
                    <li className="flex gap-2"><span className="text-purple-600">•</span> {language === 'hi' ? 'व्यापक ग्रेड कवरेज' : 'Comprehensive grade coverage'}</li>
                    <li className="flex gap-2"><span className="text-purple-600">•</span> {language === 'hi' ? 'OCR और भाषण-से-पाठ एकीकरण' : 'OCR & speech-to-text integration'}</li>
                    <li className="flex gap-2"><span className="text-purple-600">•</span> {language === 'hi' ? 'पूर्ण बहुभाषी ज्ञान आधार' : 'Complete multilingual knowledge base'}</li>
                  </ul>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* CTA Section - Enhanced */}
      <section className="bg-gradient-to-r from-blue-600 to-indigo-600 py-20">
        <div className="max-w-7xl mx-auto px-6 text-center">
          <h2 className="text-3xl sm:text-4xl font-extrabold text-white mb-8">
            {language === 'hi' ? 'क्या आप अपनी कक्षा को बदलने के लिए तैयार हैं?' : 'Ready to Transform Your Classroom?'}
          </h2>
          <button 
            onClick={() => window.location.href = '/register'} 
            className="px-8 py-4 bg-white text-blue-600 hover:bg-gray-100 font-bold rounded-xl transition-all duration-200 transform hover:-translate-y-0.5 shadow-lg hover:shadow-xl"
          >
            {language === 'hi' ? 'अभी शुरू करें' : 'Get Started Now'}
          </button>
        </div>
      </section>
    </div>
  );
}