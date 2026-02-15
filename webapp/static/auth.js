// Глобальные переменные
let currentUser = null;
let authToken = null;
let currentSessionId = null;
let sessions = [];

// Инициализация при загрузке страницы
// Проверяем состояние DOM - если скрипт загружен после DOMContentLoaded,
// событие уже произошло и обработчик не вызовется
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        initAuth();
        setupModalHandlers();
        setupSidebar();
    });
} else {
    // DOM уже готов - вызываем сразу
    initAuth();
    setupModalHandlers();
    setupSidebar();
}

// ============ АВТОРИЗАЦИЯ ============

function initAuth() {
    // Проверяем наличие токена в localStorage
    authToken = localStorage.getItem('auth_token');
    
    if (authToken) {
        // Проверяем валидность токена
        fetch('/api/auth/me', {
            headers: {
                'Authorization': `Bearer ${authToken}`
            }
        })
        .then(res => {
            if (res.ok) return res.json();
            throw new Error('Invalid token');
        })
        .then(data => {
            currentUser = data;
            showAuthenticatedUI();
            loadSessions();
        })
        .catch(() => {
            // Токен невалиден
            logout();
        });
    } else {
        showUnauthenticatedUI();
    }
}

function showAuthenticatedUI() {
    // Sidebar
    document.getElementById('sidebarUserInfo').style.display = 'block';
    document.getElementById('sidebarUserEmail').textContent = currentUser.email;
    document.getElementById('sidebarAuthSection').style.display = 'none';
    
    // На десктопе показываем sidebar
    if (window.innerWidth > 768) {
        document.getElementById('sidebar').classList.remove('mobile-hidden');
    }
}

function showUnauthenticatedUI() {
    // Sidebar
    document.getElementById('sidebarUserInfo').style.display = 'none';
    document.getElementById('sidebarAuthSection').style.display = 'block';
    
    // Скрываем sidebar
    document.getElementById('sidebar').classList.add('mobile-hidden');
}

function logout() {
    localStorage.removeItem('auth_token');
    authToken = null;
    currentUser = null;
    showUnauthenticatedUI();
    window.location.reload();
}

// ============ МОДАЛЬНЫЕ ОКНА ============

function setupModalHandlers() {
    // Закрытие по клику вне модального окна
    document.querySelectorAll('.modal').forEach(modal => {
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                closeModal(modal.id);
            }
        });
    });
    
    // Обработчики кнопок
    document.getElementById('showLoginBtn')?.addEventListener('click', () => showModal('loginModal'));
    document.getElementById('showRegisterBtn')?.addEventListener('click', () => showModal('registerModal'));
    document.getElementById('showForgotPasswordFromLogin')?.addEventListener('click', () => {
        closeModal('loginModal');
        showModal('forgotPasswordModal');
    });
    document.getElementById('showLoginFromRegister')?.addEventListener('click', () => {
        closeModal('registerModal');
        showModal('loginModal');
    });
    document.getElementById('showLoginFromForgot')?.addEventListener('click', () => {
        closeModal('forgotPasswordModal');
        showModal('loginModal');
    });
    document.getElementById('backToLoginFromVerify')?.addEventListener('click', () => {
        closeModal('verifyEmailModal');
        showModal('loginModal');
    });
    document.getElementById('resendVerificationCode')?.addEventListener('click', handleResendCode);
    
    // Формы
    document.getElementById('loginForm')?.addEventListener('submit', handleLogin);
    document.getElementById('registerForm')?.addEventListener('submit', handleRegister);
    document.getElementById('verifyEmailForm')?.addEventListener('submit', handleVerifyEmail);
    document.getElementById('forgotPasswordForm')?.addEventListener('submit', handleForgotPassword);
    document.getElementById('verifyResetCodeForm')?.addEventListener('submit', handleVerifyResetCode);
    document.getElementById('resetPasswordForm')?.addEventListener('submit', handleResetPassword);
    
    // Logout
    document.getElementById('sidebarLogoutBtn')?.addEventListener('click', logout);
}

function showModal(modalId) {
    document.getElementById(modalId).classList.add('active');
    clearModalErrors(modalId);
}

function closeModal(modalId) {
    document.getElementById(modalId).classList.remove('active');
    clearModalErrors(modalId);
}

function closeAllModals() {
    const modals = ['loginModal', 'registerModal', 'verifyEmailModal', 'forgotPasswordModal', 'verifyResetCodeModal', 'resetPasswordModal'];
    modals.forEach(modalId => {
        const modal = document.getElementById(modalId);
        if (modal) {
            modal.classList.remove('active');
            clearModalErrors(modalId);
        }
    });
}

function showModalError(modalId, message) {
    const modal = document.getElementById(modalId);
    let errorDiv = modal.querySelector('.error-message');
    if (!errorDiv) {
        errorDiv = document.createElement('div');
        errorDiv.className = 'error-message';
        modal.querySelector('.modal-body').insertBefore(errorDiv, modal.querySelector('.modal-body').firstChild);
    }
    errorDiv.textContent = message;
    errorDiv.style.display = 'block';
}

function showModalSuccess(modalId, message) {
    const modal = document.getElementById(modalId);
    let successDiv = modal.querySelector('.success-message');
    if (!successDiv) {
        successDiv = document.createElement('div');
        successDiv.className = 'success-message';
        modal.querySelector('.modal-body').insertBefore(successDiv, modal.querySelector('.modal-body').firstChild);
    }
    successDiv.textContent = message;
    successDiv.style.display = 'block';
}

function clearModalErrors(modalId) {
    const modal = document.getElementById(modalId);
    const errorDiv = modal.querySelector('.error-message');
    const successDiv = modal.querySelector('.success-message');
    if (errorDiv) errorDiv.style.display = 'none';
    if (successDiv) successDiv.style.display = 'none';
}

// ============ ОБРАБОТЧИКИ ФОРМ ============

async function handleLogin(e) {
    e.preventDefault();
    const email = document.getElementById('loginEmail').value;
    const password = document.getElementById('loginPassword').value;
    
    try {
        const res = await fetch('/api/auth/login', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({email, password})
        });
        
        const data = await res.json();
        
        if (!res.ok) {
            // Если email не верифицирован, показываем окно верификации
            if (data.error === 'Email not verified') {
                // Сохраняем email и user_id
                tempEmail = email;
                if (data.user_id) {
                    tempUserId = data.user_id;
                }
                
                // Отправляем новый код верификации
                try {
                    await fetch('/api/auth/resend-verification', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({email: email})
                    });
                } catch (e) {
                    console.error('Failed to resend code:', e);
                }
                
                closeModal('loginModal');
                showModal('verifyEmailModal');
                showModalSuccess('verifyEmailModal', 'Код верификации отправлен на ' + email + '. Проверьте почту (возможно в папке спам).');
                document.getElementById('verifyEmailCode').focus();
                return;
            }
            throw new Error(data.error || 'Ошибка входа');
        }
        
        // Сохраняем токен
        authToken = data.token;
        localStorage.setItem('auth_token', authToken);
        currentUser = data.user;
        
        closeAllModals();
        showAuthenticatedUI();
        loadSessions();
    } catch (error) {
        showModalError('loginModal', error.message);
    }
}

async function handleRegister(e) {
    e.preventDefault();
    const email = document.getElementById('registerEmail').value;
    const password = document.getElementById('registerPassword').value;
    const username = document.getElementById('registerUsername').value;
    
    try {
        const res = await fetch('/api/auth/register', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({email, password, username})
        });
        
        const data = await res.json();
        
        if (!res.ok) {
            throw new Error(data.error || 'Ошибка регистрации');
        }
        
        // Сохраняем user_id для верификации
        tempUserId = data.user_id;
        tempEmail = email;
        
        // Не закрываем окно регистрации, показываем сообщение
        showModalSuccess('registerModal', 'Код верификации отправлен на ' + email + '. Проверьте почту (возможно в папке спам).');
        
        // Через 2 секунды переключаемся на окно верификации
        setTimeout(() => {
            closeModal('registerModal');
            showModal('verifyEmailModal');
            document.getElementById('verifyEmailCode').focus();
        }, 2000);
    } catch (error) {
        showModalError('registerModal', error.message);
    }
}

let tempUserId = null;
let tempEmail = null;
let tempResetCode = null;

async function handleResendCode() {
    if (!tempEmail) {
        showModalError('verifyEmailModal', 'Ошибка: нет данных для повторной отправки');
        return;
    }
    
    try {
        const res = await fetch('/api/auth/resend-verification', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({email: tempEmail})
        });
        
        const data = await res.json();
        
        if (!res.ok) {
            throw new Error(data.error || 'Ошибка повторной отправки');
        }
        
        showModalSuccess('verifyEmailModal', 'Код повторно отправлен на ' + tempEmail + '. Проверьте папку Спам.');
    } catch (error) {
        showModalError('verifyEmailModal', error.message);
    }
}

async function handleVerifyEmail(e) {
    e.preventDefault();
    const code = document.getElementById('verifyEmailCode').value;
    
    try {
        const res = await fetch('/api/auth/verify-email', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({user_id: tempUserId, code})
        });
        
        const data = await res.json();
        
        if (!res.ok) {
            throw new Error(data.error || 'Неверный код');
        }
        
        // Сохраняем токен
        authToken = data.token;
        localStorage.setItem('auth_token', authToken);
        currentUser = data.user;
        
        closeAllModals();
        showAuthenticatedUI();
        loadSessions();
    } catch (error) {
        showModalError('verifyEmailModal', error.message);
    }
}

async function handleForgotPassword(e) {
    e.preventDefault();
    const email = document.getElementById('forgotEmail').value;
    
    try {
        const res = await fetch('/api/auth/forgot-password', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({email})
        });
        
        const data = await res.json();
        
        if (!res.ok) {
            throw new Error(data.error || 'Ошибка отправки кода');
        }
        
        tempEmail = email;
        closeModal('forgotPasswordModal');
        showModal('verifyResetCodeModal');
        showModalSuccess('verifyResetCodeModal', 'Код восстановления отправлен на ' + email);
    } catch (error) {
        showModalError('forgotPasswordModal', error.message);
    }
}

async function handleVerifyResetCode(e) {
    e.preventDefault();
    const code = document.getElementById('resetCode').value;
    
    try {
        const res = await fetch('/api/auth/verify-reset-code', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({email: tempEmail, code})
        });
        
        const data = await res.json();
        
        if (!res.ok) {
            throw new Error(data.error || 'Неверный код');
        }
        
        tempResetCode = code;
        closeModal('verifyResetCodeModal');
        showModal('resetPasswordModal');
    } catch (error) {
        showModalError('verifyResetCodeModal', error.message);
    }
}

async function handleResetPassword(e) {
    e.preventDefault();
    const newPassword = document.getElementById('newPassword').value;
    
    try {
        const res = await fetch('/api/auth/reset-password', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({email: tempEmail, code: tempResetCode, new_password: newPassword})
        });
        
        const data = await res.json();
        
        if (!res.ok) {
            throw new Error(data.error || 'Ошибка сброса пароля');
        }
        
        closeModal('resetPasswordModal');
        showModal('loginModal');
        showModalSuccess('loginModal', 'Пароль успешно изменен. Войдите с новым паролем.');
    } catch (error) {
        showModalError('resetPasswordModal', error.message);
    }
}

// ============ SIDEBAR И ИСТОРИЯ ЧАТОВ ============

function setupSidebar() {
    document.getElementById('newChatBtn')?.addEventListener('click', createNewChat);
}

async function loadSessions() {
    if (!authToken) return;
    
    try {
        const res = await fetch('/api/chat/sessions', {
            headers: {
                'Authorization': `Bearer ${authToken}`
            }
        });
        
        if (!res.ok) throw new Error('Failed to load sessions');
        
        const data = await res.json();
        sessions = data.sessions || [];
        renderSessions();
    } catch (error) {
        console.error('Error loading sessions:', error);
    }
}

function renderSessions() {
    const sessionsList = document.getElementById('sessionsList');
    if (!sessionsList) return;
    
    if (sessions.length === 0) {
        sessionsList.innerHTML = '<div style="padding: 20px; text-align: center; color: #6f6f6f; font-size: 14px;">Нет диалогов</div>';
        return;
    }
    
    sessionsList.innerHTML = sessions.map(session => {
        const date = new Date(session.created_at).toLocaleDateString('ru-RU');
        const isActive = session.id === currentSessionId;
        
        return `
            <div class="session-item ${isActive ? 'active' : ''}" data-session-id="${session.id}">
                <div class="session-title">${session.title || 'Новый чат'}</div>
                <div class="session-date">${date}</div>
                <div class="session-actions">
                    <button class="session-action-btn" onclick="renameSession(${session.id})" title="Переименовать">✏️</button>
                    <button class="session-action-btn" onclick="deleteSession(${session.id})" title="Удалить">🗑️</button>
                </div>
            </div>
        `;
    }).join('');
    
    // Добавляем обработчики кликов
    sessionsList.querySelectorAll('.session-item').forEach(item => {
        item.addEventListener('click', (e) => {
            if (!e.target.classList.contains('session-action-btn')) {
                const sessionId = parseInt(item.dataset.sessionId);
                loadSession(sessionId);
            }
        });
    });
}

async function createNewChat() {
    currentSessionId = null;
    document.getElementById('messagesContainer').innerHTML = `
        <div class="empty-state">
            <div class="empty-icon">💬</div>
            <div class="empty-title">Новый чат</div>
            <div class="empty-text">Задайте вопрос, чтобы начать диалог</div>
        </div>
    `;
    
    // Убираем активность со всех сессий
    document.querySelectorAll('.session-item').forEach(item => {
        item.classList.remove('active');
    });
}

async function loadSession(sessionId) {
    if (!authToken) return;
    
    try {
        const res = await fetch(`/api/chat/sessions/${sessionId}`, {
            headers: {
                'Authorization': `Bearer ${authToken}`
            }
        });
        
        if (!res.ok) throw new Error('Failed to load session');
        
        const data = await res.json();
        const messages = data.messages || [];
        
        currentSessionId = sessionId;
        
        // Очищаем контейнер сообщений
        const container = document.getElementById('messagesContainer');
        container.innerHTML = '';
        
        // Отображаем сообщения
        messages.forEach(msg => {
            addMessage(msg.role, msg.content, null, false);
        });
        
        // Обновляем активную сессию в списке
        document.querySelectorAll('.session-item').forEach(item => {
            item.classList.toggle('active', parseInt(item.dataset.sessionId) === sessionId);
        });
        
        // Закрываем sidebar на мобильных устройствах
        if (window.closeSidebarOnMobile) {
            window.closeSidebarOnMobile();
        }
        
    } catch (error) {
        console.error('Error loading session:', error);
    }
}

async function renameSession(sessionId) {
    const newTitle = prompt('Введите новое название:');
    if (!newTitle || !authToken) return;
    
    try {
        const res = await fetch(`/api/chat/sessions/${sessionId}`, {
            method: 'PATCH',
            headers: {
                'Authorization': `Bearer ${authToken}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({title: newTitle})
        });
        
        if (!res.ok) throw new Error('Failed to rename session');
        
        await loadSessions();
    } catch (error) {
        alert('Ошибка переименования: ' + error.message);
    }
}

async function deleteSession(sessionId) {
    if (!confirm('Удалить этот диалог?') || !authToken) return;
    
    try {
        const res = await fetch(`/api/chat/sessions/${sessionId}`, {
            method: 'DELETE',
            headers: {
                'Authorization': `Bearer ${authToken}`
            }
        });
        
        if (!res.ok) throw new Error('Failed to delete session');
        
        if (currentSessionId === sessionId) {
            createNewChat();
        }
        
        await loadSessions();
    } catch (error) {
        alert('Ошибка удаления: ' + error.message);
    }
}

// ============ ОБНОВЛЕНИЕ ФУНКЦИИ ПОИСКА ============

// Переопределяем глобальную функцию search для работы с авторизацией
window.originalSearch = window.search;
window.search = async function() {
    const input = document.getElementById('queryInput');
    const query = input.value.trim();
    if (!query || window.isLoading) return;

    // Проверяем авторизацию — без токена показываем окно входа и подсказку в чате
    if (!authToken) {
        showModal('loginModal');
        const emptyState = document.getElementById('emptyState');
        if (emptyState) emptyState.style.display = 'none';
        addMessage('user', query);
        input.value = '';
        addMessage('assistant', 'Войдите в аккаунт, чтобы задать вопрос (кнопка «Войти» вверху).');
        return;
    }
    
    // Скрываем empty state
    const emptyState = document.querySelector('.empty-state');
    if (emptyState) emptyState.style.display = 'none';
    
    // Добавляем вопрос
    addMessage('user', query);
    input.value = '';
    
    // Показываем загрузку
    window.isLoading = true;
    document.getElementById('sendBtn').disabled = true;
    const loadingId = addLoadingMessage();
    
    try {
        const response = await fetch('/api/search', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${authToken}`
            },
            body: JSON.stringify({
                query: query,
                session_id: currentSessionId
            })
        });
        
        const data = await response.json();
        document.getElementById(loadingId).remove();

        if (!response.ok) {
            const errText = data.error || data.message || `Ошибка ${response.status}`;
            addMessage('assistant', '⚠️ ' + errText + (response.status === 401 ? ' Войдите снова.' : ''));
            return;
        }

        const answer = data.answer != null ? data.answer : 'Нет ответа от сервера.';
        addMessage('assistant', answer, data.sources);
        
        if (data.session_id) {
            currentSessionId = data.session_id;
            await loadSessions();
        }
        
    } catch (error) {
        document.getElementById(loadingId).remove();
        addMessage('assistant', 'Ошибка соединения: ' + error.message);
    } finally {
        window.isLoading = false;
        document.getElementById('sendBtn').disabled = false;
    }
};
