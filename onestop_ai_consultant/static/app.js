// Client-side interactions

// Show clicked thumbnail as main image
function swapThumb(el) {
  const main = document.getElementById('mainImg');
  if (el && el.src) {
    main.src = el.src;
  }
  document.querySelectorAll('.thumb').forEach((t) => t.classList.remove('active'));
  if (el) {
    el.classList.add('active');
  }
}

// Simple cart message
function addToCart() {
  alert('Added to cart');
}

// Toggle the wishlist heart and rely on CSS for appearance
function toggleHeart() {
  const btn = document.querySelector('.heart');
  if (!btn) return;
  btn.classList.toggle('active');
}

// Open chat window
function openChat() {
  document.getElementById('chatWidget').classList.remove('hidden');
  const fab = document.getElementById('chatFab');
  if (fab) {
    fab.classList.add('hidden');
  }
  // Wait a moment
  setTimeout(() => document.getElementById('chatMsg').focus(), 100);
  loadHistory();
}

// Close chat window
function closeChat() {
  document.getElementById('chatWidget').classList.add('hidden');
  const fab = document.getElementById('chatFab');
  if (fab) {
    fab.classList.remove('hidden');
  }
}

// Pre-fill chat with a topic
function preAsk(topic) {
  openChat();
  const el = document.getElementById('chatMsg');
  el.value = topic + ' for this product please';
  el.focus();
}

// Send user message to the backend
async function sendMsg() {
  const input = document.getElementById('chatMsg');
  const msg = input.value.trim();
  if (!msg) {
    return;
  }
  input.value = '';
  const body = document.getElementById('chatBody');
  appendBubble(body, msg, 'user');

  const widget = document.getElementById('chatWidget');
  const slug = widget.dataset.slug || 'galaxy-s25-ultra';

  // In this simplified prototype always uses the model

  appendBubble(body, 'thinking', 'ai');

  try {
    const res = await fetch('/api/ask', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: msg, slug }),
    });
    const data = await res.json();
    body.lastChild.textContent = data.reply || '(no reply)';
    body.lastChild.classList.add('ai');
  } catch (e) {
    body.lastChild.textContent = '(failed to reach AI)';
  }
  body.scrollTop = body.scrollHeight;
}

// Add a chat bubble to the window
function appendBubble(container, text, who) {
  const b = document.createElement('div');
  b.className = 'bubble ' + who;
  b.textContent = text;
  container.appendChild(b);
}

// Fetch and display recent chat history
async function loadHistory() {
  const widget = document.getElementById('chatWidget');
  const slug = widget.dataset.slug || 'galaxy-s25-ultra';
  try {
    const res = await fetch('/api/history?slug=' + encodeURIComponent(slug) + '&limit=20');
    const data = await res.json();
    const body = document.getElementById('chatBody');
    body.innerHTML = '';
    (data.history || []).forEach((item) => {
      if (item.user) {
        appendBubble(body, item.user, 'user');
      }
      if (item.ai) {
        // Show AI reply
        const text = item.ai;
        appendBubble(body, text, 'ai');
      }
    });
    body.scrollTop = body.scrollHeight;
  } catch (e) {
    // Ignore errors when loading history
  }
}

// Update delivery estimates based on postcode
async function updateEta() {
  const pcInput = document.getElementById('postcode');
  const pc = pcInput ? pcInput.value.trim() : '';
  const stdSpan = document.getElementById('etaStandard');
  const expSpan = document.getElementById('etaExpress');
  // Clear ETA when postcode is empty
  if (!pc) {
    if (stdSpan) stdSpan.textContent = '—';
    if (expSpan) expSpan.textContent = '—';
    return;
  }
  // Ask the server for ETA
  const res = await fetch('/api/eta', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ postcode: pc }),
  });
  const data = await res.json();
  if (stdSpan) stdSpan.textContent = data.standard;
  if (expSpan) expSpan.textContent = data.express;
}

// Open 3D viewer
function open3D() {
  document.getElementById('modal3d').classList.remove('hidden');
}

// Close 3D viewer
function close3D() {
  document.getElementById('modal3d').classList.add('hidden');
}

// Activate first thumbnail on page load
document.addEventListener('DOMContentLoaded', function () {
  const first = document.querySelector('.thumb');
  if (first && !first.classList.contains('active')) {
    first.classList.add('active');
  }
});