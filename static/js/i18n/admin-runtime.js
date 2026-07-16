(function () {
  const entries = [
    ["pageAdminDashboard", "Оперативно табло", "Operations dashboard", "Tableau de bord des opérations"],
    ["pageTodayOverview", "Преглед за днес", "Today’s overview", "Vue d’ensemble du jour"],
    ["pageOperatorConsole", "Операторска конзола", "Operator console", "Console opérateur"],
    ["pageOperations", "Операции", "Operations", "Opérations"],
    ["pagePropertyOperations", "Операции по имоти", "Property operations", "Opérations des biens"],
    ["pageProfessionals", "Професионалисти", "Professionals", "Professionnels"],
    ["pageProfessionalApplications", "Кандидатури на професионалисти", "Professional applications", "Candidatures de professionnels"],
    ["pageOwnerAccounts", "Акаунти на собственици", "Owner accounts", "Comptes propriétaires"],
    ["pageServiceRequests", "Заявки от собственици и публичната форма", "Owner and public service requests", "Demandes propriétaires et publiques"],
    ["pageRequestDetails", "Детайли за заявката", "Request details", "Détails de la demande"],
    ["pageNotifications", "Известия", "Notifications", "Notifications"],
    ["pageDirectory", "Потребители и роли", "Users and roles", "Utilisateurs et rôles"],
    ["todayWorkplace", "Днешното оперативно работно място", "Today’s operations workspace", "Espace opérationnel du jour"],
    ["priorityQueue", "Приоритетна опашка", "Priority queue", "File prioritaire"],
    ["urgentNow", "Спешно сега", "Urgent now", "Urgent maintenant"],
    ["dispatch", "Диспечиране", "Dispatch", "Répartition"],
    ["needsAssignment", "Изискват възлагане", "Needs assignment", "Attribution requise"],
    ["quickActions", "Бързи действия", "Quick actions", "Actions rapides"],
    ["lateTasks", "Просрочени задачи", "Overdue tasks", "Tâches en retard"],
    ["unassignedTasks", "Невъзложени задачи", "Unassigned tasks", "Tâches non attribuées"],
    ["waitingRequests", "Чакащи заявки", "Waiting requests", "Demandes en attente"],
    ["availableProfessionals", "Свободни професионалисти", "Available professionals", "Professionnels disponibles"],
    ["requiresAttention", "Изисква внимание", "Requires attention", "Nécessite une attention"],
    ["assignmentNeeded", "Необходимо възлагане", "Assignment needed", "Attribution nécessaire"],
    ["awaitingResponse", "Очаква отговор", "Awaiting response", "En attente de réponse"],
    ["availableForWork", "Достъпни за работа", "Available for work", "Disponibles pour intervenir"],
    ["operatorPageTitle", "Операторска конзола · BlackSea Connect", "Operator console · BlackSea Connect", "Console opérateur · BlackSea Connect"],
    ["operatorNavigation", "Операторска навигация", "Operator navigation", "Navigation opérateur"],
    ["operatorTodaySummary", "Днешен обзор", "Today’s summary", "Résumé du jour"],
    ["arrivalsToday24h", "Пристигания днес / 24 ч.", "Arrivals today / 24h", "Arrivées aujourd’hui / 24 h"],
    ["scheduledArrivals", "Планирани пристигания", "Scheduled arrivals", "Arrivées planifiées"],
    ["requests", "Заявки", "Requests", "Demandes"],
    ["ownerRequests", "Заявки от собственици", "Owner requests", "Demandes des propriétaires"],
    ["openDashboard", "Отвори таблото", "Open dashboard", "Ouvrir le tableau de bord"],
    ["openRequest", "Отвори заявката", "Open request", "Ouvrir la demande"],
    ["openCalendar", "Отвори календара", "Open calendar", "Ouvrir le calendrier"],
    ["assign", "Възложи", "Assign", "Attribuer"],
    ["todaySchedule", "Днешен график", "Today’s schedule", "Planning du jour"],
    ["directActions", "Преки действия", "Direct actions", "Actions directes"],
    ["noUrgentTasks", "Няма спешни задачи в момента.", "No urgent tasks right now.", "Aucune tâche urgente pour le moment."],
    ["urgentTasksEmptyCopy", "Просрочени, спешни и чакащи задачи ще се показват първо тук.", "Overdue, urgent, and waiting tasks will appear here first.", "Les tâches en retard, urgentes et en attente apparaîtront ici en premier."],
    ["allAssigned", "Всичко е възложено.", "Everything is assigned.", "Tout est attribué."],
    ["unassignedEmptyCopy", "Невъзложените операции ще се показват тук.", "Unassigned operations will appear here.", "Les opérations non attribuées apparaîtront ici."],
    ["noWaitingRequests", "Няма чакащи заявки.", "No waiting requests.", "Aucune demande en attente."],
    ["waitingRequestsEmptyCopy", "Нови заявки от собственици и публичната форма ще се показват тук.", "New requests from owners and the public form will appear here.", "Les nouvelles demandes des propriétaires et du formulaire public apparaîtront ici."],
    ["noEventsToday", "Няма събития за днес.", "No events today.", "Aucun événement aujourd’hui."],
    ["todayEventsEmptyCopy", "Пристигания, заминавания, почиствания, проверки и поддръжка ще се показват тук.", "Arrivals, departures, cleaning, inspections, and maintenance will appear here.", "Les arrivées, départs, ménages, inspections et interventions de maintenance apparaîtront ici."],
    ["operation", "Операция", "Operation", "Opération"],
    ["serviceRequest", "Заявка за услуга", "Service request", "Demande de service"],
    ["ownerPriority", "Собственик", "Owner", "Propriétaire"],
    ["guestArrival", "Пристигане на гост", "Guest arrival", "Arrivée d’un voyageur"],
    ["unassignedProperty", "Невъзложен имот", "Unassigned property", "Bien non attribué"],
    ["propertyPending", "Имотът предстои да бъде уточнен", "Property pending", "Bien à préciser"],
    ["noTimeSet", "Няма зададен час", "No time set", "Aucune heure définie"],
    ["createOperation", "Създай операция", "Create operation", "Créer une opération"],
    ["importReservation", "Импортирай резервация", "Import reservation", "Importer une réservation"],
    ["allStatuses", "Всички статуси", "All statuses", "Tous les statuts"],
    ["allTypes", "Всички типове", "All types", "Tous les types"],
    ["applyFilters", "Приложи филтрите", "Apply filters", "Appliquer les filtres"],
    ["clear", "Изчисти", "Clear", "Effacer"],
    ["search", "Търсене", "Search", "Recherche"],
    ["status", "Статус", "Status", "Statut"],
    ["statusNew", "Ново", "New", "Nouveau"],
    ["statusPending", "Изчаква", "Pending", "En attente"],
    ["statusCancelled", "Отменено", "Cancelled", "Annulé"],
    ["statusBlocked", "Блокирано", "Blocked", "Bloqué"],
    ["property", "Имот", "Property", "Bien"],
    ["properties", "Имоти", "Properties", "Biens"],
    ["owner", "Собственик", "Owner", "Propriétaire"],
    ["professional", "Професионалист", "Professional", "Professionnel"],
    ["priority", "Приоритет", "Priority", "Priorité"],
    ["notes", "Бележки", "Notes", "Notes"],
    ["save", "Запази", "Save", "Enregistrer"],
    ["cancel", "Отказ", "Cancel", "Annuler"],
    ["edit", "Редактирай", "Edit", "Modifier"],
    ["delete", "Изтрий", "Delete", "Supprimer"],
    ["open", "Отвори", "Open", "Ouvrir"],
    ["assigned", "Възложено", "Assigned", "Attribué"],
    ["unassigned", "Невъзложено", "Unassigned", "Non attribué"],
    ["scheduled", "Планирано", "Scheduled", "Planifié"],
    ["inProgress", "В процес", "In progress", "En cours"],
    ["completed", "Завършено", "Completed", "Terminé"],
    ["new", "Нова", "New", "Nouvelle"],
    ["active", "Активен", "Active", "Actif"],
    ["inactive", "Неактивен", "Inactive", "Inactif"],
    ["noData", "Все още няма данни.", "No data yet.", "Aucune donnée pour le moment."],
    ["calendarAdmin", "Административен календар", "Admin Calendar", "Calendrier administrateur"],
    ["calendarAttention", "Какво изисква внимание сега?", "What needs attention now?", "Que faut-il traiter maintenant ?"],
    ["calendarAnalyzing", "Анализираме днешните операции…", "Analyzing today’s operations…", "Analyse des opérations du jour…"],
    ["calendarShow", "Покажи", "Show", "Afficher"],
    ["calendarAllProperties", "Всички имоти", "All properties", "Tous les biens"],
    ["calendarWeeklySchedule", "Седмичен оперативен график", "Weekly operations schedule", "Planning opérationnel hebdomadaire"],
    ["calendarMonth", "Месец", "Month", "Mois"],
    ["calendarWeek", "Седмица", "Week", "Semaine"],
    ["calendarDay", "Ден", "Day", "Jour"],
    ["calendarTimeline", "Хронология", "Timeline", "Chronologie"],
    ["calendarMultiProperty", "Мулти имоти", "Multi-property", "Multi-biens"],
    ["calendarDispatcher", "Диспечер", "Dispatcher", "Répartition"],
    ["calendarMap", "Карта", "Map", "Carte"],
    ["calendarManagement", "Ръководство", "Management", "Gestion"],
    ["calendarFilters", "Филтри", "Filters", "Filtres"],
    ["calendarCreate", "Създай събитие", "Create event", "Créer un événement"],
    ["calendarToday", "Днес", "Today", "Aujourd’hui"],
    ["calendarTomorrow", "Утре", "Tomorrow", "Demain"],
    ["calendarCategory", "Категория", "Category", "Catégorie"],
    ["calendarFromDate", "От дата", "From date", "Date de début"],
    ["calendarToDate", "До дата", "To date", "Date de fin"],
    ["calendarAllPriorities", "Всички приоритети", "All priorities", "Toutes les priorités"],
    ["calendarAllCategories", "Всички категории", "All categories", "Toutes les catégories"],
    ["calendarEventsSearch", "Търсене в събития", "Search events", "Rechercher des événements"],
    ["calendarNeedsAttention", "Изискват внимание", "Needs attention", "À traiter"],
    ["calendarNoCritical", "Няма критични задачи.", "No critical tasks.", "Aucune tâche critique."],
    ["calendarNextAction", "Следващо действие", "Next action", "Action suivante"],
    ["calendarChooseEvent", "Изберете събитие", "Select an event", "Sélectionnez un événement"],
    ["calendarChooseDateTime", "Изберете дата и час.", "Choose a date and time.", "Choisissez une date et une heure."],
    ["calendarNewEvent", "Ново събитие", "New event", "Nouvel événement"],
    ["calendarAddSchedule", "Добавяне към графика", "Add to schedule", "Ajouter au planning"],
    ["calendarStart", "Начало", "Start", "Début"],
    ["calendarEnd", "Край", "End", "Fin"],
    ["calendarAddEvent", "Добави събитие", "Add event", "Ajouter l’événement"],
    ["calendarNoNotes", "Няма избрани бележки.", "No notes selected.", "Aucune note sélectionnée."],
    ["calendarNoWarnings", "Няма активни предупреждения.", "No active warnings.", "Aucun avertissement actif."],
    ["calendarQuickActions", "Бързи действия", "Quick actions", "Actions rapides"],
    ["calendarAssignment", "Възлагане", "Assignment", "Attribution"],
    ["calendarSaveTime", "Запази часа", "Save time", "Enregistrer l’heure"],
    ["calendarTechnical", "Техническа диагностика", "Technical diagnostics", "Diagnostic technique"],
    ["calendarEditEvent", "Редактиране на събитие", "Edit event", "Modifier l’événement"],
    ["calendarSaveChanges", "Запази промените", "Save changes", "Enregistrer les modifications"],
    ["calendarLinkProperty", "Свързване с имот", "Link to property", "Associer à un bien"],
    ["calendarChooseCanonicalProperty", "Изберете каноничен имот", "Select the canonical property", "Sélectionnez le bien de référence"],
    ["calendarUnlinkedPropertyCopy", "Календарният запис няма свързан каноничен имот.", "This calendar record has no linked canonical property.", "Cet enregistrement du calendrier n’est associé à aucun bien de référence."],
    ["calendarMatchingProperties", "Подходящи имоти", "Matching properties", "Biens correspondants"],
    ["calendarSource", "Източник", "Source", "Source"],
    ["calendarUnknownSource", "неизвестен", "unknown", "inconnue"],
    ["calendarExactPropertyName", "точно име на имота", "exact property name", "nom exact du bien"],
    ["calendarMatchingOwner", "съвпадащ собственик", "matching owner", "propriétaire correspondant"],
    ["calendarMatchingCity", "съвпадащ град", "matching city", "ville correspondante"],
    ["calendarNoMatchingProperty", "Няма намерен подходящ имот", "No matching property found", "Aucun bien correspondant trouvé"],
    ["calendarPropertyRequiredBeforeLink", "Преди събитието да бъде свързано, имотът трябва първо да съществува.", "A property must exist before this event can be linked.", "Un bien doit d’abord exister avant que cet événement puisse y être associé."],
    ["calendarCreateProperty", "Създай нов имот", "Create a new property", "Créer un nouveau bien"],
    ["calendarOpenProperties", "Отвори списъка с имоти", "Open properties list", "Ouvrir la liste des biens"],
    ["calendarCancel", "Отказ", "Cancel", "Annuler"],
    ["calendarLinkToProperty", "Свържи с имот", "Link to property", "Associer au bien"],
    ["calendarProfessionalAssignment", "Професионално възлагане", "Professional assignment", "Attribution à un professionnel"],
    ["calendarChooseProfessional", "Изберете професионалист", "Select a professional", "Sélectionnez un professionnel"],
    ["calendarConfirmConflict", "Потвърждавам възлагане въпреки конфликт в графика", "I confirm assignment despite a schedule conflict", "Je confirme l’attribution malgré un conflit de planning"],
    ["calendarAssignNow", "Възложи сега", "Assign now", "Attribuer maintenant"],
    ["calendarTimeCorrection", "Корекция на часа", "Time correction", "Correction de l’horaire"],
    ["calendarStartEnd", "Начало и край", "Start and end", "Début et fin"],
    ["calendarSelectProperty", "Изберете имот", "Select a property", "Sélectionnez un bien"],
    ["calendarSelectValidProperty", "Изберете валиден имот.", "Select a valid property.", "Sélectionnez un bien valide."],
    ["calendarNoOwner", "Без собственик", "No owner", "Sans propriétaire"],
    ["calendarNotAssigned", "Не е възложено", "Unassigned", "Non attribué"],
    ["eventOther", "Друга услуга", "Other service", "Autre service"],
    ["eventReservation", "Резервация", "Reservation", "Réservation"],
    ["eventCleaning", "Почистване", "Cleaning", "Ménage"],
    ["eventArrival", "Пристигане", "Arrival", "Arrivée"],
    ["eventDeparture", "Заминаване", "Departure", "Départ"],
    ["eventInspection", "Инспекция", "Inspection", "Inspection"],
    ["eventMaintenance", "Поддръжка", "Maintenance", "Maintenance"],
    ["eventEmergency", "Спешен случай", "Emergency", "Urgence"],
    ["eventProfessionalVisit", "Посещение на професионалист", "Professional visit", "Visite d’un professionnel"],
    ["eventOwnerMeeting", "Среща със собственик", "Owner meeting", "Rendez-vous avec le propriétaire"],
    ["eventTransfer", "Трансфер", "Transfer", "Transfert"],
    ["eventBlockedDates", "Блокирани дати", "Blocked dates", "Dates bloquées"],
    ["eventPersonalStay", "Личен престой", "Personal stay", "Séjour personnel"],
    ["priorityLow", "Нисък", "Low", "Faible"],
    ["priorityNormal", "Нормален", "Normal", "Normal"],
    ["priorityMedium", "Среден", "Medium", "Moyen"],
    ["priorityHigh", "Висок", "High", "Élevé"],
    ["priorityUrgent", "Спешен", "Urgent", "Urgent"],
    ["priorityCritical", "Критичен", "Critical", "Critique"],
    ["placeholderPrivateNotes", "Поверителни бележки за админ екипа", "Private notes for the admin team", "Notes privées pour l’équipe admin"],
    ["placeholderOperationalNote", "Вътрешна оперативна бележка", "Internal operations note", "Note opérationnelle interne"],
    ["backToDashboard", "Към таблото", "Back to dashboard", "Retour au tableau de bord"],
    ["backToCockpit", "Назад към управленския панел", "Back to cockpit", "Retour au cockpit"],
    ["viewAll", "Виж всички", "View all", "Tout afficher"],
    ["total", "Общо", "Total", "Total"],
    ["created", "Създаден", "Created", "Créé"],
    ["createdAt", "Дата на създаване", "Creation date", "Date de création"],
    ["cityLocation", "Град / местоположение", "City / location", "Ville / localisation"],
    ["propertyType", "Тип имот", "Property type", "Type de bien"],
    ["capacity", "Капацитет", "Capacity", "Capacité"],
    ["activeProperties", "Активни имоти", "Active properties", "Biens actifs"],
    ["seasonalProperties", "Сезонни имоти", "Seasonal properties", "Biens saisonniers"],
    ["inactiveProperties", "Неактивни имоти", "Inactive properties", "Biens inactifs"],
    ["totalProperties", "Общо имоти", "Total properties", "Total des biens"],
    ["noFilteredProperties", "Няма имоти, които отговарят на филтрите.", "No properties match the filters.", "Aucun bien ne correspond aux filtres."],
    ["propertyDetails", "Property details", "Property details", "Détails du bien"],
    ["currentReadiness", "Current readiness", "Current readiness", "État de préparation"],
    ["miniCalendar", "Mini calendar", "Mini calendar", "Mini-calendrier"],
    ["latestRequests", "Latest linked requests", "Latest linked requests", "Dernières demandes liées"],
    ["ownerCalendarBlocks", "Owner calendar blocks", "Owner calendar blocks", "Blocages calendrier du propriétaire"],
    ["ownerProfile", "Owner profile", "Owner profile", "Profil propriétaire"],
    ["adminNotes", "Admin notes", "Admin notes", "Notes administrateur"],
    ["propertyTimeline", "Property timeline", "Property timeline", "Chronologie du bien"],
    ["saveNotes", "Save notes", "Save notes", "Enregistrer les notes"],
    ["noTimeline", "No timeline entries yet.", "No timeline entries yet.", "Aucune entrée dans la chronologie."],
    ["professionalApplications", "Professional application detail", "Professional application detail", "Détail de la candidature professionnelle"],
    ["reviewApplication", "Review professional application", "Review professional application", "Examiner la candidature professionnelle"],
    ["updateStatus", "Update status", "Update status", "Mettre à jour le statut"],
    ["internalNotes", "Internal notes", "Internal notes", "Notes internes"],
    ["saveApplication", "Save application", "Save application", "Enregistrer la candidature"],
    ["activityHistory", "Activity history", "Activity history", "Historique d’activité"],
    ["newestFirst", "Newest first", "Newest first", "Plus récents d’abord"],
    ["noActivity", "No activity yet.", "No activity yet.", "Aucune activité pour le moment."],
    ["exportCsv", "Експорт CSV", "Export CSV", "Exporter en CSV"],
    ["totalApplications", "Общо кандидатури", "Total applications", "Total des candidatures"],
    ["qualified", "Квалифицирани", "Qualified", "Qualifiées"],
    ["converted", "Конвертирани", "Converted", "Converties"],
    ["lost", "Отпаднали", "Lost", "Perdues"],
    ["noApplications", "Все още няма кандидатури.", "No applications yet.", "Aucune candidature pour le moment."],
    ["requestActions", "Request actions", "Request actions", "Actions sur la demande"],
    ["operationalControls", "Operational controls", "Operational controls", "Contrôles opérationnels"],
    ["closeRequest", "Close request", "Close request", "Clôturer la demande"],
    ["archiveRequest", "Archive request", "Archive request", "Archiver la demande"],
    ["duplicateRequest", "Duplicate request", "Duplicate request", "Dupliquer la demande"],
    ["deleteRequest", "Изтрий заявката", "Delete request", "Supprimer la demande"],
    ["confirmDeletion", "Потвърждение", "Confirm deletion", "Confirmer la suppression"],
    ["requestDescription", "Request description", "Request description", "Description de la demande"],
    ["whatOwnerAsked", "What the owner asked for", "What the owner asked for", "Demande du propriétaire"],
    ["assignedProfessional", "Assigned professional", "Assigned professional", "Professionnel attribué"],
    ["noProfessional", "No professional selected", "No professional selected", "Aucun professionnel sélectionné"],
    ["matchedProfessionals", "Matched professionals", "Matched professionals", "Professionnels correspondants"],
    ["saveRequest", "Save request", "Save request", "Enregistrer la demande"],
    ["timeline", "Хронология", "Timeline", "Chronologie"],
    ["recycleBin", "Кошче", "Recycle bin", "Corbeille"],
    ["allLanguages", "All languages", "All languages", "Toutes les langues"],
    ["reset", "Изчисти", "Reset", "Réinitialiser"],
    ["openProfile", "Open profile", "Open profile", "Ouvrir le profil"],
    ["propertyCount", "Property count", "Property count", "Nombre de biens"],
    ["lastLogin", "Last login", "Last login", "Dernière connexion"],
    ["linkedProperties", "Linked properties", "Linked properties", "Biens liés"],
    ["accountDetails", "Account details", "Account details", "Détails du compte"],
    ["activitySummary", "Account activity summary", "Account activity summary", "Résumé de l’activité du compte"],
    ["statusNotes", "Status and internal notes", "Status and internal notes", "Statut et notes internes"],
    ["ownerTimeline", "Owner timeline", "Owner timeline", "Chronologie du propriétaire"],
    ["archiveOwner", "Archive owner", "Archive owner", "Archiver le propriétaire"],
    ["saveOwner", "Save owner", "Save owner", "Enregistrer le propriétaire"],
    ["settings", "Settings", "Settings", "Paramètres"],
    ["alerts", "Alerts", "Alerts", "Alertes"],
    ["recentAlerts", "Recent alerts", "Recent alerts", "Alertes récentes"],
    ["overdueAlerts", "Overdue alerts", "Overdue alerts", "Alertes en retard"],
    ["failedNotifications", "Failed notifications", "Failed notifications", "Notifications échouées"],
    ["savePreferences", "Save preferences", "Save preferences", "Enregistrer les préférences"],
    ["noAlerts", "No alerts yet.", "No alerts yet.", "Aucune alerte pour le moment."],
    ["users", "Потребители", "Users", "Utilisateurs"],
    ["roles", "Роли", "Roles", "Rôles"],
    ["roleMatrix", "Матрица на ролите", "Role matrix", "Matrice des rôles"],
    ["inviteUser", "Покани потребител", "Invite user", "Inviter un utilisateur"],
    ["access", "Достъп", "Access", "Accès"],
    ["scope", "Обхват", "Scope", "Périmètre"],
    ["role", "Роля", "Role", "Rôle"],
    ["type", "Тип", "Type", "Type"],
    ["name", "Име", "Name", "Nom"]
  ];

  const module = { bg: { admin: {} }, en: { admin: {} }, fr: { admin: {} } };
  entries.forEach(function (entry) {
    module.bg.admin[entry[0]] = entry[1];
    module.en.admin[entry[0]] = entry[2];
    module.fr.admin[entry[0]] = entry[3];
  });
  window.BlackSeaI18NModules = window.BlackSeaI18NModules || {};
  window.BlackSeaI18NModules.adminRuntime = module;

  if (!window.location || !String(window.location.pathname || "").startsWith("/admin")) {
    return;
  }

  const phraseToKey = new Map();
  entries.forEach(function (entry) {
    entry.slice(1).forEach(function (phrase) { phraseToKey.set(phrase, entry[0]); });
  });

  function language() {
    const value = String(document.documentElement.lang || "bg").toLowerCase();
    return ["bg", "en", "fr"].includes(value) ? value : "en";
  }

  function translation(key, lang) {
    const dictionary = (window.BlackSeaI18N || {})[lang] || {};
    return dictionary.admin && dictionary.admin[key];
  }

  function translateValue(value, lang) {
    const raw = String(value || "");
    const trimmed = raw.trim();
    const key = phraseToKey.get(trimmed);
    if (!key) return raw;
    const translated = translation(key, lang);
    if (!translated) return raw;
    return raw.replace(trimmed, translated);
  }

  function localizeElement(element, lang) {
    if (!element || element.nodeType !== 1 || element.matches("script,style,[data-admin-no-i18n]") || element.closest("[data-admin-no-i18n]")) return;
    if (!element.hasAttribute("data-i18n")) {
      Array.from(element.childNodes || []).forEach(function (node) {
        if (node.nodeType === 3) node.nodeValue = translateValue(node.nodeValue, lang);
      });
    }
    ["placeholder", "title", "aria-label"].forEach(function (attribute) {
      if (element.hasAttribute(attribute) && !element.hasAttribute("data-i18n-attr")) {
        element.setAttribute(attribute, translateValue(element.getAttribute(attribute), lang));
      }
    });
  }

  function localize(root) {
    const lang = language();
    if (!root) return;
    if (root.nodeType === 1) localizeElement(root, lang);
    if (typeof root.querySelectorAll === "function") {
      root.querySelectorAll("*").forEach(function (element) { localizeElement(element, lang); });
    }
  }

  function boot() {
    localize(document.body);
    window.addEventListener("blacksea:languagechange", function () { localize(document.body); });
    if (typeof MutationObserver === "function") {
      const observer = new MutationObserver(function (mutations) {
        mutations.forEach(function (mutation) {
          mutation.addedNodes.forEach(function (node) { localize(node); });
        });
      });
      observer.observe(document.body, { childList: true, subtree: true });
    }
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot, { once: true });
  else boot();
}());
