(function () {
  const uploadZone = document.querySelector('[data-owner-upload-zone]');
  const photoInput = document.querySelector('[data-owner-photo-input]');
  const gallery = document.querySelector('[data-owner-gallery]');
  const galleryOrderInput = document.querySelector('[data-gallery-order]');
  const deletePhotoIdsInput = document.querySelector('[data-delete-photo-ids]');
  const deleteDocumentIdsInput = document.querySelector('[data-delete-document-ids]');

  if (uploadZone && photoInput) {
    const syncDroppedFiles = (files) => {
      if (!files || !files.length) {
        return;
      }
      const dataTransfer = new DataTransfer();
      for (const file of photoInput.files) {
        dataTransfer.items.add(file);
      }
      for (const file of files) {
        dataTransfer.items.add(file);
      }
      photoInput.files = dataTransfer.files;
    };

    uploadZone.addEventListener('dragover', (event) => {
      event.preventDefault();
      uploadZone.classList.add('is-dragging');
    });

    uploadZone.addEventListener('dragleave', () => {
      uploadZone.classList.remove('is-dragging');
    });

    uploadZone.addEventListener('drop', (event) => {
      event.preventDefault();
      uploadZone.classList.remove('is-dragging');
      syncDroppedFiles(event.dataTransfer.files);
    });
  }

  if (!gallery || !galleryOrderInput || !deletePhotoIdsInput) {
    return;
  }

  const deletedPhotoIds = new Set();

  const syncHiddenInputs = () => {
    const itemIds = [];
    gallery.querySelectorAll('[data-owner-gallery-item]').forEach((item) => {
      const photoId = item.dataset.photoId;
      if (photoId) {
        itemIds.push(photoId);
      }
    });
    galleryOrderInput.value = itemIds.join(',');
    deletePhotoIdsInput.value = Array.from(deletedPhotoIds).join(',');
  };

  const moveItem = (item, direction) => {
    const sibling = direction === 'up' ? item.previousElementSibling : item.nextElementSibling;
    if (!sibling || !sibling.matches('[data-owner-gallery-item]')) {
      return;
    }
    if (direction === 'up') {
      gallery.insertBefore(item, sibling);
    } else {
      gallery.insertBefore(sibling, item);
    }
    syncHiddenInputs();
  };

  gallery.addEventListener('click', (event) => {
    const target = event.target.closest('[data-gallery-move], [data-gallery-delete]');
    if (!target) {
      return;
    }

    const item = target.closest('[data-owner-gallery-item]');
    if (!item) {
      return;
    }

    const photoId = item.dataset.photoId;
    if (target.hasAttribute('data-gallery-delete')) {
      if (photoId) {
        deletedPhotoIds.add(photoId);
      }
      item.remove();
      syncHiddenInputs();
      return;
    }

    const direction = target.getAttribute('data-gallery-move');
    moveItem(item, direction);
  });

  if (deleteDocumentIdsInput) {
    const documentDeletes = new Set();
    const syncDocumentDeletes = () => {
      deleteDocumentIdsInput.value = Array.from(documentDeletes).join(',');
    };
    document.querySelectorAll('[data-owner-document-item]').forEach((item) => {
      const removeButton = item.querySelector('[data-document-delete]');
      if (!removeButton) {
        return;
      }
      removeButton.addEventListener('click', () => {
        const documentId = item.dataset.documentId;
        if (documentId) {
          documentDeletes.add(documentId);
        }
        item.remove();
        syncDocumentDeletes();
      });
    });
  }

  syncHiddenInputs();
})();
