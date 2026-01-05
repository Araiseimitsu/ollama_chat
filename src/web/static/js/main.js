const chatContainer = document.getElementById('chat-messages');
const form = document.getElementById('chat-form');
const input = document.getElementById('user-input');
const submitBtn = document.getElementById('submit-btn');
const imageInput = document.getElementById('image-input');
const imagePicker = document.getElementById('image-picker');
const imageClear = document.getElementById('image-clear');
const imagePreview = document.getElementById('image-preview');

// ストリーミングモードの切り替え（デフォルトはtrue）
const USE_STREAMING = true;
let activeStreamController = null;
let scrollPending = false;

function scrollToBottom() {
    chatContainer.scrollTop = chatContainer.scrollHeight;
}

function scheduleScroll() {
    if (scrollPending) return;
    scrollPending = true;
    requestAnimationFrame(() => {
        scrollToBottom();
        scrollPending = false;
    });
}

// テキストエリアの高さを自動調整
function autoResizeTextarea() {
    input.style.height = 'auto';
    input.style.height = Math.min(input.scrollHeight, 96) + 'px';
}

// 初期化時に高さを設定
autoResizeTextarea();

// 入力時に高さを調整
input.addEventListener('input', autoResizeTextarea);

if (imagePicker && imageInput) {
    imagePicker.addEventListener('click', () => {
        imageInput.click();
    });
}

if (imageInput) {
    imageInput.addEventListener('change', updateImagePreview);
}

if (imageClear) {
    imageClear.addEventListener('click', clearImages);
}

// Shift + Enterで改行、Enterのみで送信
input.addEventListener('keydown', function (e) {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        form.requestSubmit();
    }
});

function setLoading(isLoading) {
    if (isLoading) {
        form.classList.add('is-loading');
    } else {
        form.classList.remove('is-loading');
    }
    input.disabled = isLoading;
    submitBtn.disabled = false;
    if (imageInput) imageInput.disabled = isLoading;
    if (imagePicker) imagePicker.disabled = isLoading;
    if (imageClear) imageClear.disabled = isLoading;
    if (submitBtn) {
        submitBtn.setAttribute('aria-label', isLoading ? '停止' : '送信');
    }
}

function buildImagePreviewHtml(imageUrls) {
    if (!imageUrls || !imageUrls.length) return '';
    const imagesHtml = imageUrls
        .map(url => `<img src="${url}" class="message-image" alt="uploaded image">`)
        .join('');
    return `<div class="message-images">${imagesHtml}</div>`;
}

function appendUserMessage(message, imageUrls = []) {
    const imageHtml = buildImagePreviewHtml(imageUrls);
    const textHtml = message
        ? `<div class="rounded-2xl px-5 py-3 shadow-sm backdrop-blur-sm text-sm md:text-base leading-relaxed whitespace-pre-wrap bg-gradient-to-br from-blue-500 to-blue-600 text-white rounded-br-none">${escapeHtml(message)}</div>`
        : '';
    const userMsgHtml = `<div class="flex w-full justify-end items-end space-x-2"><div class="max-w-[80%]">${imageHtml}${textHtml}</div><div class="flex-shrink-0 w-8 h-8 rounded-full bg-gray-200 flex items-center justify-center text-gray-500 shadow-sm mb-1"><svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M10 9a3 3 0 100-6 3 3 0 000 6zm-7 9a7 7 0 1114 0H3z" clip-rule="evenodd" /></svg></div></div>`;
    chatContainer.insertAdjacentHTML('beforeend', userMsgHtml);
    scheduleScroll();
}

function updateImagePreview() {
    if (!imageInput || !imagePreview || !imageClear) return;

    const files = Array.from(imageInput.files || []);
    imagePreview.innerHTML = '';

    if (!files.length) {
        imagePreview.classList.add('is-hidden');
        imageClear.classList.add('is-hidden');
        return;
    }

    imagePreview.classList.remove('is-hidden');
    imageClear.classList.remove('is-hidden');

    files.forEach((file) => {
        const reader = new FileReader();
        reader.onload = (evt) => {
            const wrapper = document.createElement('div');
            wrapper.className = 'image-preview-item';
            const img = document.createElement('img');
            img.src = evt.target.result;
            img.alt = file.name || 'uploaded image';
            wrapper.appendChild(img);
            imagePreview.appendChild(wrapper);
        };
        reader.readAsDataURL(file);
    });
}

function clearImages() {
    if (!imageInput) return;
    imageInput.value = '';
    updateImagePreview();
}

function getPreviewSources() {
    if (!imagePreview) return [];
    return Array.from(imagePreview.querySelectorAll('img'))
        .map(img => img.src)
        .filter(Boolean);
}

function createAssistantMessage() {
    const wrapper = document.createElement('div');
    wrapper.className = 'flex w-full justify-start items-end space-x-2';

    const avatar = document.createElement('div');
    avatar.className = 'flex-shrink-0 w-8 h-8 rounded-full bg-gradient-to-br from-blue-400 to-purple-500 flex items-center justify-center text-white shadow-sm mb-1';
    avatar.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM7 9H5v2h2V9zm8 0h-2v2h2V9zM9 9h2v2H9V9z" clip-rule="evenodd" /></svg>';

    const contentWrapper = document.createElement('div');
    contentWrapper.className = 'max-w-[80%]';

    const thinkingContainer = document.createElement('div');
    thinkingContainer.className = 'thinking-container is-hidden';

    const thinkingToggle = document.createElement('div');
    thinkingToggle.className = 'thinking-toggle thinking-live';

    const thinkingIcon = document.createElement('span');
    thinkingIcon.className = 'thinking-toggle-icon';
    thinkingIcon.textContent = '?';

    const thinkingLabel = document.createElement('span');
    thinkingLabel.className = 'thinking-toggle-label';
    thinkingLabel.textContent = '思考中';

    thinkingToggle.appendChild(thinkingIcon);
    thinkingToggle.appendChild(thinkingLabel);

    const thinkingContent = document.createElement('div');
    thinkingContent.className = 'thinking-content';

    thinkingContainer.appendChild(thinkingToggle);
    thinkingContainer.appendChild(thinkingContent);

    const responseBubble = document.createElement('div');
    responseBubble.className = 'assistant-response rounded-2xl px-5 py-3 shadow-sm backdrop-blur-sm text-sm md:text-base leading-relaxed whitespace-pre-wrap bg-white/80 text-gray-800 border border-white/50 rounded-bl-none';

    contentWrapper.appendChild(thinkingContainer);
    contentWrapper.appendChild(responseBubble);

    wrapper.appendChild(avatar);
    wrapper.appendChild(contentWrapper);

    chatContainer.appendChild(wrapper);
    scheduleScroll();

    return {
        wrapper,
        responseBubble,
        thinkingContainer,
        thinkingToggle,
        thinkingLabel,
        thinkingContent
    };
}

function getLastLines(text, lineCount) {
    if (!text) return '';
    const lines = text.split(/\r?\n/);
    return lines.slice(Math.max(lines.length - lineCount, 0)).join('\n');
}

async function streamChat(formData) {
    if (activeStreamController) {
        activeStreamController.abort();
    }

    const assistant = createAssistantMessage();
    const responseBubble = assistant.responseBubble;
    const thinkingContainer = assistant.thinkingContainer;
    const thinkingToggle = assistant.thinkingToggle;
    const thinkingLabel = assistant.thinkingLabel;
    const thinkingContent = assistant.thinkingContent;

    let responseText = '';
    let thinkingText = '';

    responseBubble.classList.add('streaming');
    setLoading(true);

    const controller = new AbortController();
    activeStreamController = controller;

    const updateResponse = () => {
        responseBubble.textContent = responseText;
        scheduleScroll();
    };

    const updateThinking = () => {
        if (!thinkingText) return;
        thinkingContainer.classList.remove('is-hidden');
        thinkingToggle.classList.add('thinking-live');
        thinkingLabel.textContent = '思考中';
        thinkingContent.classList.add('thinking-live-preview');
        thinkingContent.textContent = getLastLines(thinkingText, 3);
        scheduleScroll();
    };

    const finalize = () => {
        responseBubble.classList.remove('streaming');
        if (thinkingText) {
            thinkingToggle.classList.remove('thinking-live');
            thinkingLabel.textContent = '思考過程を表示';
            thinkingContent.classList.remove('thinking-live-preview');
            thinkingContent.textContent = thinkingText;
        } else {
            thinkingContainer.classList.add('is-hidden');
        }
        scheduleScroll();
        input.focus();
    };

    const handlePayload = (payload) => {
        if (!payload || !payload.type) return;

        if (payload.type === 'thinking') {
            thinkingText += payload.content || '';
            updateThinking();
        } else if (payload.type === 'response') {
            responseText += payload.content || '';
            updateResponse();
        } else if (payload.type === 'error') {
            responseText = payload.content || 'エラーが発生しました。';
            responseBubble.classList.add('assistant-error');
            updateResponse();
        }
    };

    const processBuffer = (buffer) => {
        const events = buffer.split('\n\n');
        const remainder = events.pop() || '';

        events.forEach((eventChunk) => {
            const dataLines = eventChunk
                .split('\n')
                .filter(line => line.startsWith('data:'));

            if (!dataLines.length) return;

            const dataText = dataLines
                .map(line => line.slice(5).trimStart())
                .join('\n');

            if (!dataText) return;

            try {
                const payload = JSON.parse(dataText);
                if (payload.type === 'done') {
                    return;
                }
                handlePayload(payload);
            } catch (error) {
                console.warn('SSE JSON parse error:', error);
            }
        });

        return remainder;
    };

    try {
        const response = await fetch('/chat/stream', {
            method: 'POST',
            body: formData,
            signal: controller.signal
        });

        if (!response.ok || !response.body) {
            throw new Error(`サーバーとの通信に失敗しました (HTTP ${response.status})`);
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder('utf-8');
        let buffer = '';

        while (true) {
            const { value, done } = await reader.read();
            if (done) break;
            buffer += decoder.decode(value, { stream: true });
            buffer = processBuffer(buffer);
        }

        if (buffer.trim()) {
            processBuffer(buffer);
        }
    } catch (error) {
        responseBubble.classList.remove('streaming');
        responseBubble.classList.add('assistant-error');
        if (error.name === 'AbortError') {
            responseBubble.textContent = 'ストリーミングが中断されました。';
        } else {
            responseBubble.textContent = `エラーが発生しました: ${error.message || error}`;
        }
    } finally {
        finalize();
        setLoading(false);
        if (activeStreamController === controller) {
            activeStreamController = null;
        }
    }
}

function handleStreamingSubmit(evt) {
    if (!USE_STREAMING) return;

    evt.preventDefault();
    evt.stopImmediatePropagation();

    const message = input.value.trim();
    const hasImages = imageInput && imageInput.files && imageInput.files.length > 0;
    if (!message && !hasImages) return;

    const previewUrls = getPreviewSources();

    appendUserMessage(message, previewUrls);

    setTimeout(() => {
        input.value = '';
        autoResizeTextarea();
        input.focus();
    }, 10);

    const formData = new FormData(form);
    formData.set('user_input', message);
    streamChat(formData);
    clearImages();
}

if (USE_STREAMING) {
    form.addEventListener('submit', handleStreamingSubmit, true);
}

if (submitBtn) {
    submitBtn.addEventListener('click', (evt) => {
        if (!USE_STREAMING) return;
        if (!form.classList.contains('is-loading')) return;
        evt.preventDefault();
        evt.stopPropagation();
        if (activeStreamController) {
            activeStreamController.abort();
        }
    });
}

// htmxのリクエスト開始前イベントをキャッチ
form.addEventListener('htmx:beforeRequest', function (evt) {
    if (USE_STREAMING) {
        evt.preventDefault();
        return;
    }
    const message = input.value.trim();
    const hasImages = imageInput && imageInput.files && imageInput.files.length > 0;
    if (!message && !hasImages) {
        evt.preventDefault();
        return;
    }

    const previewUrls = getPreviewSources();

    // ユーザーメッセージのHTMLテンプレート（partials/chat_history.htmlと同じ構造）
    appendUserMessage(message, previewUrls);

    // 入力をクリア
    setTimeout(() => {
        input.value = '';
        autoResizeTextarea();
    }, 10);

    clearImages();
});

// サーバーからの応答後にスクロール
form.addEventListener('htmx:afterOnLoad', function (evt) {
    if (USE_STREAMING) return;
    scrollToBottom();
});

// HTMLエスケープ関数（簡易版）
function escapeHtml(text) {
    return text
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

// MutationObserverを使って初期ロード時などの追加にも反応
const observer = new MutationObserver(scrollToBottom);
observer.observe(chatContainer, { childList: true, subtree: true });

// Thinking ブロックの折りたたみ機能
function initThinkingToggles() {
    const toggleButtons = document.querySelectorAll('.thinking-toggle');

    toggleButtons.forEach(button => {
        // 既にイベントリスナーが設定されている場合はスキップ
        if (button.dataset.initialized) return;
        button.dataset.initialized = 'true';

        button.addEventListener('click', function() {
            const container = this.closest('.thinking-container');
            const content = container.querySelector('.thinking-content');

            // トグル状態を切り替え
            this.classList.toggle('expanded');
            content.classList.toggle('expanded');
        });
    });
}

// 初期ロード時に実行
initThinkingToggles();

// DOMの変更を監視してthinkingトグルを初期化
const thinkingObserver = new MutationObserver(() => {
    initThinkingToggles();
});

thinkingObserver.observe(chatContainer, {
    childList: true,
    subtree: true
});
