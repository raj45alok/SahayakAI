import React, { useState, useEffect } from 'react';
import { Navbar } from '../layout/Navbar';
import { ChevronLeft, ChevronRight, Cloud, Zap, BarChart3 } from 'lucide-react';
import { ImageWithFallback } from '../figma/ImageWithFallback';
import { useLanguage } from '../i18n/LanguageContext';

export function AboutPage() {
  const { language } = useLanguage(); // Only use `language`, not `t`
  const [currentImage, setCurrentImage] = useState(0);
  
  const storyImages = [
    '/story/scene1.jpg',
    '/story/scene2.jpg',
    '/story/scene3.jpg',
    '/story/scene4.jpg'
  ];

  useEffect(() => {
    const interval = setInterval(() => {
      setCurrentImage((prev) => (prev === storyImages.length - 1 ? 0 : prev + 1));
    }, 10000);
    return () => clearInterval(interval);
  }, [storyImages.length]);

  const handlePrevImage = () => {
    setCurrentImage((prev) => (prev === 0 ? storyImages.length - 1 : prev - 1));
  };

  const handleNextImage = () => {
    setCurrentImage((prev) => (prev === storyImages.length - 1 ? 0 : prev + 1));
  };

  const team = [
    {
      name: "Alok",
      role: "Team Lead & Application Designer",
      description: language === 'hi'
        ? "सहायक एआई के दृष्टिकोण और डिज़ाइन दर्शन का नेतृत्व करते हैं। सहज इंटरफेस बनाते हैं और संदेह समाधानकर्ता व अनुसूचित सामग्री वितरण जैसी मुख्य सुविधाओं का नेतृत्व करते हैं।"
        : "Leading the vision and design philosophy of Sahayak AI. Crafting intuitive interfaces and spearheading core features like Doubt Solver and Scheduled Content Delivery."
    },
    {
      name: "Pranay",
      role: "ML & Operations",
      description: language === 'hi'
        ? "व्यक्तिगत सीखने की सिफारिशों और सामग्री वृद्धि के लिए मशीन लर्निंग मॉडल बना रहे हैं और उन्हें अनुकूलित कर रहे हैं।"
        : "Building and optimizing the machine learning models that power personalized learning recommendations and content enhancement."
    },
    {
      name: "Samarth",
      role: "ML & Operations",
      description: language === 'hi'
        ? "छात्र प्रदर्शन का विश्लेषण करने और वास्तविक समय में सीखने के अनुभव को अनुकूलित करने वाले एल्गोरिदम विकसित कर रहे हैं।"
        : "Developing algorithms that analyze student performance and adapt the learning experience in real-time with intelligent grading systems."
    },
    {
      name: "Mayan",
      role: "ML & Operations",
      description: language === 'hi'
        ? "एमएल पाइपलाइन को सुचारू रूप से संचालित करना सुनिश्चित करते हैं — कुशल डेटा प्रसंस्करण, मॉडल तैनाती और वर्कशीट उत्पादन।"
        : "Ensuring the ML pipeline operates smoothly with efficient data processing, model deployment, and worksheet generation."
    },
    {
      name: "Shashwat",
      role: "Frontend Development & Integration",
      description: language === 'hi'
        ? "सभी उपकरणों पर सहायक एआई को जीवंत बनाने वाले प्रतिक्रियाशील और गतिशील उपयोगकर्ता इंटरफेस बना रहे हैं।"
        : "Creating responsive and dynamic user interfaces that bring Sahayak AI to life across all devices with React and Tailwind CSS."
    },
    {
      name: "Akshika",
      role: "Frontend Development & Integration",
      description: language === 'hi'
        ? "सुचारू एपीआई एकीकरण बना रही हैं और सुगम उपयोगकर्ता अंतःक्रियाओं के लिए फ्रंटएंड प्रदर्शन को अनुकूलित कर रही हैं।"
        : "Building seamless API integrations and optimizing frontend performance for smooth user interactions and comprehensive testing."
    }
  ];

  return (
    <div className="min-h-screen bg-background">
      <Navbar />
      
      {/* Hero Section */}
      <section className="py-20 px-4 sm:px-6 lg:px-8 bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900">
        <div className="max-w-7xl mx-auto">
          <div className="grid lg:grid-cols-2 gap-12 items-center">
            <div className="space-y-6">
              <h1 className="text-5xl lg:text-6xl font-bold text-orange-400">
                {language === 'hi' ? 'सहायक एआई' : 'Sahayak AI'}
              </h1>
              <div className="flex items-center gap-3 mb-4">
                <Cloud className="w-6 h-6 text-orange-400" />
                <span className="text-lg font-semibold text-orange-400">
                  {language === 'hi' ? 'AWS क्लाउड सेवाओं द्वारा संचालित' : 'Powered by AWS Cloud Services'}
                </span>
              </div>
              <p className="text-xl text-gray-300 leading-relaxed font-medium">
                {language === 'hi'
                  ? 'भारतीय मध्य विद्यालय शिक्षकों (कक्षा 6–8) के लिए AWS क्लाउड बुनियादी ढांचे पर निर्मित एक स्वायत्त एआई-संचालित कक्षा सहायक।'
                  : 'An autonomous AI-powered classroom assistant built on AWS cloud infrastructure for Indian middle school teachers (Grades 6–8).'}
              </p>
              <p className="text-lg text-gray-400 leading-relaxed font-bold">
                {language === 'hi'
                  ? 'AWS Bedrock का उपयोग बुद्धिमान सामग्री वितरण के लिए, AWS Lambda का उपयोग स्वायत्त अनुसूचन के लिए, और AWS SageMaker का उपयोग अनुकूली सीखने के लिए — सहायक एआई शिक्षकों के पढ़ाने और छात्रों के सीखने के तरीके को बदल देता है।'
                  : 'Leveraging AWS Bedrock for intelligent content delivery, AWS Lambda for autonomous scheduling, and AWS SageMaker for adaptive learning — Sahayak AI transforms how teachers teach and students learn.'}
              </p>
              <p className="text-lg text-gray-400 leading-relaxed">
                {language === 'hi'
                  ? 'हमारी प्रणाली प्रशासनिक भार को कम करती है, सगाई को बढ़ाती है, और विविध भारतीय कक्षाओं में व्यक्तिगत शिक्षा को बड़े पैमाने पर सक्षम करती है।'
                  : 'Our system reduces administrative burden, enhances engagement, and personalizes education at scale across diverse Indian classrooms.'}
              </p>
              <p className="text-lg text-gray-400 leading-relaxed">
                {language === 'hi'
                  ? 'ग्रामीण और शहरी स्कूलों दोनों के लिए पहुंच, बहुभाषी समर्थन और ऑफ़लाइन-पहले क्षमताओं पर ध्यान केंद्रित करके निर्मित।'
                  : 'Built with a focus on accessibility, multilingual support, and offline-first capabilities for rural and urban schools alike.'}
              </p>
              <p className="text-lg text-gray-400 leading-relaxed">
                {language === 'hi'
                  ? 'जिम्मेदार, शिक्षक-केंद्रित एआई के माध्यम से शिक्षा के भविष्य को फिर से सोचने में हमारे साथ शामिल हों।'
                  : 'Join us in reimagining the future of education through responsible, teacher-centric AI.'}
              </p>
            </div>
            
            <div className="relative">
              <ImageWithFallback 
                src={require('../../assets/SahayakAiAbout.png')}
                alt={language === 'hi' ? 'सहायक एआई - बुद्धिमान शिक्षा' : 'Sahayak AI - Intelligent Education'}
                className="rounded-2xl shadow-2xl w-full h-auto"
              />
            </div>
          </div>
        </div>
      </section>

      {/* Mission & Vision */}
      <section className="py-20 px-4 sm:px-6 lg:px-8 bg-white">
        <div className="max-w-7xl mx-auto">
          <div className="text-center mb-16">
            <h2 className="text-4xl font-bold text-gray-900 mb-4">
              {language === 'hi' ? 'मिशन और दृष्टि' : 'Mission & Vision'}
            </h2>
            <p className="text-lg text-gray-700">
              {language === 'hi'
                ? 'हम सहायक एआई क्यों बना रहे हैं और हम क्या हासिल करना चाहते हैं'
                : 'Why we\'re building Sahayak AI and what we want to achieve'}
            </p>
          </div>

          <div className="grid lg:grid-cols-2 gap-8">
            {/* Mission */}
            <div className="relative overflow-hidden rounded-2xl p-8 bg-gradient-to-br from-blue-50 to-blue-100 border-2 border-blue-300 shadow-lg hover:shadow-xl transition-all">
              <div className="absolute top-0 right-0 w-40 h-40 bg-blue-200/30 rounded-full -mr-20 -mt-20"></div>
              <div className="relative z-10">
                <div className="flex items-center gap-3 mb-6">
                  <div className="w-14 h-14 rounded-lg bg-gradient-to-br from-blue-500 to-blue-700 flex items-center justify-center">
                    <Zap className="w-7 h-7 text-white" />
                  </div>
                  <h3 className="text-3xl font-bold text-gray-900">
                    {language === 'hi' ? 'मिशन' : 'Mission'}
                  </h3>
                </div>
                <p className="text-lg text-gray-800 leading-relaxed">
                  {language === 'hi'
                    ? 'कक्षा शिक्षा को स्वायत्त रूप से क्रांतिकारी बनाना ताकि प्रशासनिक कार्य स्वचालित हों और शिक्षक अर्थपूर्ण छात्र अंतःक्रिया पर ध्यान केंद्रित कर सकें। हमें विश्वास है कि प्रौद्योगिकी को शिक्षक के कार्यभार को कम करना चाहिए, न कि उसे जटिल बनाना चाहिए।'
                    : 'To autonomously revolutionize classroom education by automating administrative tasks and enabling teachers to focus on meaningful student interaction. We believe technology should reduce teacher workload, not complicate it.'}
                </p>
              </div>
            </div>

            {/* Vision */}
            <div className="relative overflow-hidden rounded-2xl p-8 bg-gradient-to-br from-purple-50 to-purple-100 border-2 border-purple-300 shadow-lg hover:shadow-xl transition-all">
              <div className="absolute top-0 right-0 w-40 h-40 bg-purple-200/30 rounded-full -mr-20 -mt-20"></div>
              <div className="relative z-10">
                <div className="flex items-center gap-3 mb-6">
                  <div className="w-14 h-14 rounded-lg bg-gradient-to-br from-purple-500 to-purple-700 flex items-center justify-center">
                    <BarChart3 className="w-7 h-7 text-white" />
                  </div>
                  <h3 className="text-3xl font-bold text-gray-900">
                    {language === 'hi' ? 'दृष्टि' : 'Vision'}
                  </h3>
                </div>
                <p className="text-lg text-gray-800 leading-relaxed">
                  {language === 'hi'
                    ? 'एक ऐसा भविष्य जहां भारत का हर छात्र व्यक्तिगत, बुद्धिमान सीखने के अनुभवों तक पहुंच सके। हम कक्षाओं की कल्पना करते हैं जहां एआई दैनिक कार्य संभालता है, शिक्षक सबसे महत्वपूर्ण चीज़ों पर ध्यान केंद्रित करते हैं, और हर छात्र को अपनी अद्वितीय आवश्यकताओं और गति के अनुसार अनुकूली, बहुभाषी शिक्षा प्राप्त होती है।'
                    : 'A future where every student in India has access to personalized, intelligent learning experiences. We envision classrooms where AI handles routine tasks, teachers focus on what matters most, and every student receives adaptive, multilingual education tailored to their unique needs and pace.'}
                </p>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Our Story */}
      <section className="py-20 px-4 sm:px-6 lg:px-8 bg-gradient-to-br from-gray-50 to-gray-100">
        <div className="max-w-7xl mx-auto">
          <div className="text-center mb-16">
            <h2 className="text-4xl font-bold text-gray-900 mb-4">
              {language === 'hi' ? 'हमारी कहानी' : 'Our Story'}
            </h2>
            <p className="text-lg text-gray-600 max-w-3xl mx-auto">
              {language === 'hi'
                ? 'वह यात्रा जिसने हमें बुद्धिमान एआई प्रौद्योगिकी के साथ शिक्षा को बदलने के लिए प्रेरित किया। स्वचालित रूप से घूमने वाली गैलरी हमारे विकास के मील के पत्थर दिखाती है।'
                : 'The journey that led us to transform education with intelligent AI technology. Auto-rotating gallery showing our development milestones.'}
            </p>
          </div>
          
          <div className="flex justify-center items-center">
            <div className="relative w-full max-w-4xl">
              <div className="relative h-96 flex items-center justify-center">
                <button
                  onClick={handlePrevImage}
                  className="absolute left-0 z-10 bg-gradient-to-r from-blue-600 to-purple-600 text-white rounded-full p-3 shadow-lg hover:shadow-xl transition-all hover:scale-110"
                  aria-label={language === 'hi' ? 'पिछली छवि' : 'Previous image'}
                >
                  <ChevronLeft className="w-6 h-6" />
                </button>
                
                <div className="relative w-full max-w-2xl h-full flex items-center justify-center">
                  <img
                    key={currentImage}
                    src={storyImages[currentImage]}
                    alt={`${language === 'hi' ? 'कहानी दृश्य' : 'Story scene'} ${currentImage + 1}`}
                    className="w-full h-full object-contain rounded-2xl shadow-2xl transition-all duration-700 ease-in-out"
                    onError={(e) => {
                      e.currentTarget.src = 'https://via.placeholder.com/800x600?text=Image+Not+Found';
                    }}
                  />
                </div>
                
                <button
                  onClick={handleNextImage}
                  className="absolute right-0 z-10 bg-gradient-to-r from-blue-600 to-purple-600 text-white rounded-full p-3 shadow-lg hover:shadow-xl transition-all hover:scale-110"
                  aria-label={language === 'hi' ? 'अगली छवि' : 'Next image'}
                >
                  <ChevronRight className="w-6 h-6" />
                </button>
              </div>
              
              <div className="flex justify-center mt-8 gap-3">
                {storyImages.map((_, index) => (
                  <button
                    key={index}
                    onClick={() => setCurrentImage(index)}
                    className={`transition-all duration-300 rounded-full ${
                      currentImage === index 
                        ? 'bg-gradient-to-r from-blue-600 to-purple-600 w-8 h-3' 
                        : 'bg-gray-300 w-3 h-3 hover:bg-gray-400'
                    }`}
                    aria-label={`${language === 'hi' ? 'छवि पर जाएं' : 'Go to image'} ${index + 1}`}
                  />
                ))}
              </div>

              <div className="text-center mt-4">
                <p className="text-sm text-gray-600">
                  {language === 'hi' ? '10 सेकंड में स्वचालित रूप से घूमता है' : 'Auto-rotating every 10 seconds'}
                </p>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Team */}
      <section className="py-20 px-4 sm:px-6 lg:px-8 bg-white">
        <div className="max-w-7xl mx-auto">
          <div className="text-center mb-16">
            <h2 className="text-4xl font-bold text-gray-900 mb-4">
              {language === 'hi' ? 'हमारी टीम से मिलें' : 'Meet Our Team'}
            </h2>
            <p className="text-lg text-gray-700 max-w-3xl mx-auto">
              {language === 'hi'
                ? 'एक उत्साही छात्र समूह जो AWS-संचालित एआई, स्वायत्तता और नवाचार के माध्यम से शिक्षा को बदलने के लिए समर्पित है।'
                : 'A passionate group of students dedicated to transforming education through AWS-powered AI, autonomy, and innovation.'}
            </p>
          </div>
          
          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
            {team.map((member, index) => (
              <div key={index} className="bg-gradient-to-br from-slate-50 to-slate-100 rounded-xl p-6 shadow-md hover:shadow-lg transition-all border border-slate-200">
                <div className="space-y-4">
                  <div>
                    <h3 className="text-xl font-bold text-gray-900">{member.name}</h3>
                    <p className="text-sm font-semibold text-blue-600 mt-1">{member.role}</p>
                  </div>
                  <p className="text-sm text-gray-700 leading-relaxed">
                    {member.description}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="py-20 px-4 sm:px-6 lg:px-8 bg-gradient-to-r from-slate-900 via-orange-900 to-slate-900">
        <div className="max-w-4xl mx-auto text-center">
          <div className="flex items-center justify-center gap-3 mb-6">
            <Cloud className="w-8 h-8 text-orange-400" />
            <span className="text-orange-400 font-semibold">
              {language === 'hi' ? 'AWS वैश्विक एआई एजेंटिक हैकाथॉन' : 'Sahayk Powered by AWS'}
            </span>
          </div>
          <h2 className="text-4xl font-bold text-white mb-6">
            {language === 'hi' ? 'बुद्धिमान शिक्षा का अनुभव लेने के लिए तैयार हैं?' : 'Ready to Experience Intelligent Learning?'}
          </h2>
          <p className="text-xl text-gray-300 mb-8">
            {language === 'hi'
              ? 'खोजें कि कैसे सहायक एआई AWS-संचालित स्वायत्त एजेंट के साथ कक्षाओं को बदलता है, शिक्षकों को सशक्त बनाता है, और व्यक्तिगत शिक्षा के माध्यम से छात्र क्षमता को अनलॉक करता है।'
              : 'Discover how Sahayak AI transforms classrooms with AWS-powered autonomous agents, empowers teachers, and unlocks student potential through personalized education.'}
          </p>
          <button 
            onClick={() => window.location.href = '/register'}
            className="px-8 py-4 bg-orange-500 text-white font-bold rounded-lg hover:bg-orange-600 transition-colors shadow-lg hover:shadow-xl"
          >
            {language === 'hi' ? 'आज ही शुरू करें' : 'Get Started Today'}
          </button>
        </div>
      </section>
    </div>
  );
}