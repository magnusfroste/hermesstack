/**
 * AI Bridge Plugin - Frontend
 * Lägger till AI Chat flik i Hermes UI
 */

(function() {
  'use strict';

  const { React, hooks, components, api } = window.__HERMES_PLUGIN_SDK__;
  const { useState, useEffect } = hooks;
  const { Card, Button, Input, Badge } = components;

  // Huvudkomponent
  function AIBridgePanel() {
    const [messages, setMessages] = useState([]);
    const [input, setInput] = useState('');
    const [sessionId, setSessionId] = useState(null);
    const [status, setStatus] = useState('idle');

    // Skapa session vid start
    useEffect(() => {
      createSession();
    }, []);

    async function createSession() {
      try {
        const response = await api.createSession({ name: 'AI Bridge' });
        setSessionId(response.id);
      } catch (err) {
        console.error('Failed to create session:', err);
      }
    }

    async function sendMessage() {
      if (!input.trim() || !sessionId) return;

      setStatus('sending');
      
      try {
        // Skicka till backend
        const response = await fetch('/api/ai-bridge/chat', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            message: input,
            session_id: sessionId
          })
        });

        const data = await response.json();
        
        if (data.success) {
          setMessages(prev => [...prev, 
            { role: 'user', content: input },
            { role: 'assistant', content: 'Processing...' }
          ]);
          setInput('');
          
          // Polla efter svar
          pollForResponse(sessionId);
        }
      } catch (err) {
        console.error('Error:', err);
        setStatus('error');
      }
    }

    async function pollForResponse(sid) {
      // Vänta och hämta senaste meddelanden
      setTimeout(async () => {
        try {
          const response = await fetch(`/api/ai-bridge/sessions/${sid}/messages`);
          const data = await response.json();
          
          // Uppdatera meddelanden
          if (Array.isArray(data)) {
            setMessages(data);
          }
          setStatus('idle');
        } catch (err) {
          console.error('Poll error:', err);
        }
      }, 2000);
    }

    return React.createElement('div', { className: 'p-4' },
      React.createElement(Card, { className: 'mb-4' },
        React.createElement('h2', { className: 'text-lg font-bold mb-2' }, 
          '🤖 AI Bridge'
        ),
        React.createElement('p', { className: 'text-sm text-gray-600' },
          'Direct communication channel for AI assistant'
        ),
        sessionId && React.createElement(Badge, { variant: 'success' }, 
          `Session: ${sessionId.slice(0, 8)}...`
        )
      ),

      // Meddelandelista
      React.createElement(Card, { className: 'mb-4 min-h-[300px]' },
        messages.length === 0 
          ? React.createElement('p', { className: 'text-gray-500 text-center' },
              'No messages yet. Start a conversation!'
            )
          : messages.map((msg, i) => 
              React.createElement('div', { 
                key: i,
                className: `mb-2 p-2 rounded ${
                  msg.role === 'user' ? 'bg-blue-100 ml-8' : 'bg-gray-100 mr-8'
                }`
              },
                React.createElement('strong', null, msg.role === 'user' ? 'You: ' : 'Hermes: '),
                React.createElement('span', null, msg.content)
              )
            )
      ),

      // Input
      React.createElement('div', { className: 'flex gap-2' },
        React.createElement(Input, {
          value: input,
          onChange: (e) => setInput(e.target.value),
          placeholder: 'Ask something...',
          className: 'flex-1',
          onKeyDown: (e) => e.key === 'Enter' && sendMessage()
        }),
        React.createElement(Button, {
          onClick: sendMessage,
          disabled: status === 'sending' || !input.trim()
        }, status === 'sending' ? 'Sending...' : 'Send')
      )
    );
  }

  // Registrera plugin
  if (window.__HERMES_PLUGIN_SDK__) {
    window.__HERMES_PLUGIN_SDK__.registerPlugin('ai-bridge', {
      name: 'AI Bridge',
      icon: 'bot',
      component: AIBridgePanel,
      backend: '/api/ai-bridge'
    });
    console.log('✅ AI Bridge plugin registered');
  } else {
    console.error('❌ Hermes Plugin SDK not found');
  }
})();
