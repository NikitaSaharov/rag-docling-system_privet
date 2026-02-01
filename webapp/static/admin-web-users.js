// Добавить пункт меню "Web Пользователи" если его нет
function initWebUsersTab() {
    const sidebar = document.querySelector('.sidebar');
    if (!sidebar) return;
    
    // Проверяем, есть ли уже пункт меню
    if (!document.getElementById('webUsersMenuItem')) {
        const menuItem = document.createElement('div');
        menuItem.id = 'webUsersMenuItem';
        menuItem.className = 'menu-item';
        menuItem.innerHTML = '👥 Web Пользователи';
        menuItem.onclick = () => showTab('webusers');
        
        // Добавляем после первого пункта
        const firstItem = sidebar.querySelector('.menu-item');
        if (firstItem) {
            firstItem.parentNode.insertBefore(menuItem, firstItem.nextSibling);
        }
    }
    
    // Создаем контент для вкладки если его нет
    if (!document.getElementById('webusersList')) {
        const content = document.querySelector('.content');
        if (content) {
            const webUsersSection = document.createElement('div');
            webUsersSection.id = 'webusers-content';
            webUsersSection.className = 'tab-content';
            webUsersSection.style.display = 'none';
            webUsersSection.innerHTML = `
                <div class="card">
                    <h2 class="card-title">Web Пользователи</h2>
                    <div id="webusersTableContainer">
                        <table>
                            <thead>
                                <tr>
                                    <th>ID</th>
                                    <th>Email</th>
                                    <th>Имя</th>
                                    <th>Статус</th>
                                    <th>Верификация</th>
                                    <th>Дата регистрации</th>
                                    <th>Действия</th>
                                </tr>
                            </thead>
                            <tbody id="webusersList">
                                <tr><td colspan="7">Загрузка...</td></tr>
                            </tbody>
                        </table>
                    </div>
                </div>
            `;
            content.appendChild(webUsersSection);
        }
    }
}

// Переопределяем функцию showTab для поддержки новой вкладки
const originalShowTab = window.showTab;
window.showTab = function(tab) {
    if (tab === 'webusers') {
        // Скрываем все вкладки
        document.querySelectorAll('.tab-content').forEach(content => {
            content.style.display = 'none';
        });
        
        // Убираем активность у всех пунктов меню
        document.querySelectorAll('.menu-item').forEach(item => {
            item.classList.remove('active');
        });
        
        // Показываем вкладку web users
        const webUsersContent = document.getElementById('webusers-content');
        if (webUsersContent) {
            webUsersContent.style.display = 'block';
        }
        
        // Активируем пункт меню
        const menuItem = document.getElementById('webUsersMenuItem');
        if (menuItem) {
            menuItem.classList.add('active');
        }
        
        // Обновляем заголовок
        const headerTitle = document.querySelector('.header-title');
        if (headerTitle) {
            headerTitle.textContent = 'Web Пользователи';
        }
        
        // Загружаем данные
        loadWebUsers();
    } else if (originalShowTab) {
        originalShowTab(tab);
    }
};

// Загрузка web-пользователей
async function loadWebUsers() {
    try {
        const response = await fetch('/api/admin/web-users');
        const data = await response.json();
        
        const tbody = document.getElementById('webusersList');
        if (!tbody) return;
        
        if (data.success && data.users.length > 0) {
            tbody.innerHTML = data.users.map(user => {
                const createdAt = new Date(user.created_at).toLocaleDateString('ru-RU');
                const statusBadge = user.is_active 
                    ? '<span style="padding: 4px 8px; background: #10b981; color: white; border-radius: 4px; font-size: 12px;">Активен</span>'
                    : '<span style="padding: 4px 8px; background: #ef4444; color: white; border-radius: 4px; font-size: 12px;">Неактивен</span>';
                const verifiedBadge = user.is_verified
                    ? '<span style="padding: 4px 8px; background: #3b82f6; color: white; border-radius: 4px; font-size: 12px;">✓ Подтвержден</span>'
                    : '<span style="padding: 4px 8px; background: #f59e0b; color: white; border-radius: 4px; font-size: 12px;">Не подтвержден</span>';
                
                return `
                    <tr>
                        <td>${user.id}</td>
                        <td><strong>${user.email}</strong></td>
                        <td>${user.username || '-'}</td>
                        <td>${statusBadge}</td>
                        <td>${verifiedBadge}</td>
                        <td>${createdAt}</td>
                        <td>
                            <button class="btn btn-small" onclick="toggleWebUserActive(${user.id}, ${user.is_active})">
                                ${user.is_active ? 'Деактивировать' : 'Активировать'}
                            </button>
                            <button class="btn btn-small" onclick="viewUserSessions(${user.id}, '${user.email}')">
                                Диалоги
                            </button>
                        </td>
                    </tr>
                `;
            }).join('');
        } else {
            tbody.innerHTML = '<tr><td colspan="7" style="text-align: center; padding: 40px; color: #6f6f6f;">Нет web-пользователей</td></tr>';
        }
    } catch (error) {
        console.error('Ошибка загрузки web-пользователей:', error);
        const tbody = document.getElementById('webusersList');
        if (tbody) {
            tbody.innerHTML = '<tr><td colspan="7" style="text-align: center; padding: 40px; color: #ef4444;">Ошибка загрузки данных</td></tr>';
        }
    }
}

// Активация/деактивация пользователя
async function toggleWebUserActive(userId, currentStatus) {
    const action = currentStatus ? 'деактивировать' : 'активировать';
    if (!confirm(`Вы уверены, что хотите ${action} этого пользователя?`)) return;
    
    try {
        const response = await fetch(`/api/admin/web-users/${userId}/toggle-active`, {
            method: 'POST'
        });
        const data = await response.json();
        
        if (data.success) {
            alert(data.message);
            loadWebUsers(); // Перезагружаем список
        } else {
            alert('Ошибка: ' + data.error);
        }
    } catch (error) {
        alert('Ошибка: ' + error.message);
    }
}

// Просмотр диалогов пользователя
async function viewUserSessions(userId, userEmail) {
    try {
        const response = await fetch(`/api/admin/web-users/${userId}/sessions`);
        const data = await response.json();
        
        if (!data.success) {
            alert('Ошибка загрузки сессий: ' + data.error);
            return;
        }
        
        const sessions = data.sessions || [];
        
        if (sessions.length === 0) {
            alert('У этого пользователя пока нет диалогов');
            return;
        }
        
        // Создаем модальное окно для просмотра
        showUserSessionsModal(userId, userEmail, sessions);
    } catch (error) {
        alert('Ошибка: ' + error.message);
    }
}

// Модальное окно для просмотра сессий
function showUserSessionsModal(userId, userEmail, sessions) {
    // Удаляем старое модальное окно если есть
    const oldModal = document.getElementById('userSessionsModal');
    if (oldModal) oldModal.remove();
    
    const modal = document.createElement('div');
    modal.id = 'userSessionsModal';
    modal.style.cssText = `
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background: rgba(0, 0, 0, 0.5);
        display: flex;
        align-items: center;
        justify-content: center;
        z-index: 10000;
    `;
    
    const content = document.createElement('div');
    content.style.cssText = `
        background: white;
        border-radius: 12px;
        padding: 24px;
        max-width: 800px;
        width: 90%;
        max-height: 80vh;
        overflow-y: auto;
    `;
    
    content.innerHTML = `
        <h2 style="margin-bottom: 16px;">Диалоги пользователя: ${userEmail}</h2>
        <div>
            ${sessions.map((session, idx) => {
                const date = new Date(session.created_at).toLocaleString('ru-RU');
                return `
                    <div style="margin-bottom: 16px; padding: 16px; background: #f7f7f7; border-radius: 8px;">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                            <strong>${session.title || 'Диалог #' + (idx + 1)}</strong>
                            <span style="font-size: 12px; color: #6f6f6f;">${date}</span>
                        </div>
                        <button class="btn btn-small" onclick="loadSessionMessages(${userId}, ${session.id}, '${session.title}')">
                            Просмотреть сообщения
                        </button>
                    </div>
                `;
            }).join('')}
        </div>
        <button class="btn btn-secondary" onclick="document.getElementById('userSessionsModal').remove()" style="margin-top: 16px;">
            Закрыть
        </button>
    `;
    
    modal.appendChild(content);
    document.body.appendChild(modal);
    
    // Закрытие по клику вне окна
    modal.addEventListener('click', (e) => {
        if (e.target === modal) {
            modal.remove();
        }
    });
}

// Загрузка сообщений сессии
async function loadSessionMessages(userId, sessionId, sessionTitle) {
    try {
        const response = await fetch(`/api/admin/web-users/${userId}/sessions/${sessionId}/messages`);
        const data = await response.json();
        
        if (!data.success) {
            alert('Ошибка загрузки сообщений: ' + data.error);
            return;
        }
        
        const messages = data.messages || [];
        
        if (messages.length === 0) {
            alert('В этом диалоге пока нет сообщений');
            return;
        }
        
        // Показываем сообщения
        showMessagesModal(sessionTitle, messages);
    } catch (error) {
        alert('Ошибка: ' + error.message);
    }
}

// Модальное окно для просмотра сообщений
function showMessagesModal(sessionTitle, messages) {
    const oldModal = document.getElementById('messagesModal');
    if (oldModal) oldModal.remove();
    
    const modal = document.createElement('div');
    modal.id = 'messagesModal';
    modal.style.cssText = `
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background: rgba(0, 0, 0, 0.5);
        display: flex;
        align-items: center;
        justify-content: center;
        z-index: 10001;
    `;
    
    const content = document.createElement('div');
    content.style.cssText = `
        background: white;
        border-radius: 12px;
        padding: 24px;
        max-width: 900px;
        width: 90%;
        max-height: 80vh;
        overflow-y: auto;
    `;
    
    content.innerHTML = `
        <h2 style="margin-bottom: 16px;">${sessionTitle}</h2>
        <div>
            ${messages.map(msg => {
                const isUser = msg.role === 'user';
                const bgColor = isUser ? '#e3f2fd' : '#f5f5f5';
                const icon = isUser ? '👤' : '🤖';
                const time = new Date(msg.created_at).toLocaleTimeString('ru-RU');
                
                return `
                    <div style="margin-bottom: 16px; padding: 12px; background: ${bgColor}; border-radius: 8px;">
                        <div style="display: flex; gap: 12px; align-items: start;">
                            <div>${icon}</div>
                            <div style="flex: 1;">
                                <div style="font-size: 12px; color: #6f6f6f; margin-bottom: 4px;">${time}</div>
                                <div style="white-space: pre-wrap;">${msg.content}</div>
                            </div>
                        </div>
                    </div>
                `;
            }).join('')}
        </div>
        <button class="btn btn-secondary" onclick="document.getElementById('messagesModal').remove()" style="margin-top: 16px;">
            Закрыть
        </button>
    `;
    
    modal.appendChild(content);
    document.body.appendChild(modal);
    
    modal.addEventListener('click', (e) => {
        if (e.target === modal) {
            modal.remove();
        }
    });
}

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', () => {
    initWebUsersTab();
});
