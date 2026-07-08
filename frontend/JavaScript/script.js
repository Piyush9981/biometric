/**
 * script.js - User Management Module Functionality
 * 
 * This file handles frontend interactions on the User Management page:
 * - Form validation (phone number restrictions)
 * - Profile image previewing, validation, and FormData uploading
 * - Role-based dynamic form field displays (Warden vs Gatekeeper)
 * - Opening, closing, and populating modals (Create, Edit, View Details, Reset Password, and Delete)
 * - User search client-side filtering
 * 
 * Used in: HTML/user_management.html
 */

document.addEventListener('DOMContentLoaded', () => {
    // -------------------------------------------------------------
    // Element References
    // Used for selecting elements in user_management.html modal forms
    // -------------------------------------------------------------
    const userModal = document.getElementById('user-modal');
    const userForm = document.getElementById('user-form');
    const formMode = document.getElementById('form-mode');
    const userIdInput = document.getElementById('user-id');
    const fullNameInput = document.getElementById('user-full-name');
    const usernameInput = document.getElementById('user-username');
    const emailInput = document.getElementById('user-email');
    const passwordInput = document.getElementById('user-password');
    const passwordLabel = document.getElementById('password-label');
    const passwordHelp = document.getElementById('password-help');
    const roleSelect = document.getElementById('user-role');
    const hostelContainer = document.getElementById('hostel-container');
    const gateContainer = document.getElementById('gate-container');
    const purposesContainer = document.getElementById('purposes-container');
    const hostelSelect = document.getElementById('user-hostel-name');
    const gateSelect = document.getElementById('user-gate-name');
    const formMessage = document.getElementById('user-form-message');
    const saveUserBtn = document.getElementById('btn-save-user');
    const modalTitle = document.getElementById('modal-user-title');

    // -------------------------------------------------------------
    // Contact Number Input Sanitization & Limitation
    // Used in user_management.html "Register New User" / "Edit User" form
    // Prevents alphabet/special characters and limits input length to 10
    // -------------------------------------------------------------
    const contactInput = document.getElementById('user-contact');
    if (contactInput) {
        contactInput.addEventListener('input', () => {
            contactInput.value = contactInput.value.replace(/\D/g, '').substring(0, 10);
        });
    }

    // -------------------------------------------------------------
    // Reset Password Modal Elements
    // Used in user_management.html "Reset Password" dialog form
    // -------------------------------------------------------------
    const resetModal = document.getElementById('reset-password-modal');
    const resetForm = document.getElementById('reset-password-form');
    const resetUserId = document.getElementById('reset-user-id');
    const resetUsernameDisplay = document.getElementById('reset-username-display');
    const resetNewPw = document.getElementById('reset-new-password');
    const resetConfirmPw = document.getElementById('reset-confirm-password');
    const resetMessage = document.getElementById('reset-password-message');
    const savePwBtn = document.getElementById('btn-save-password');

    // -------------------------------------------------------------
    // Delete Confirmation Modal Elements
    // Used in user_management.html "Delete Account" confirmation dialog
    // -------------------------------------------------------------
    const deleteModal = document.getElementById('delete-confirm-modal');
    const deleteUsernameDisplay = document.getElementById('delete-user-name-display');
    const confirmDeleteBtn = document.getElementById('btn-confirm-delete');
    const deleteMessage = document.getElementById('delete-message');
    let targetDeleteUserId = null;

    // -------------------------------------------------------------
    // Dynamic Role-Based Select Display Listener
    // Used in user_management.html user modal form
    // Toggles Hostel selector for "Warden" role, and Gate selector for "Gatekeeper" role
    // -------------------------------------------------------------
    roleSelect.addEventListener('change', () => {
        const role = roleSelect.value;
        if (role === 'Warden') {
            hostelContainer.classList.remove('hidden');
            hostelSelect.required = true;
            purposesContainer.classList.remove('hidden');
            gateContainer.classList.add('hidden');
            gateSelect.required = false;
            gateSelect.value = '';
        } else if (role === 'Gatekeeper') {
            gateContainer.classList.remove('hidden');
            gateSelect.required = true;
            hostelContainer.classList.add('hidden');
            hostelSelect.required = false;
            hostelSelect.value = '';
            purposesContainer.classList.add('hidden');
        } else {
            hostelContainer.classList.add('hidden');
            hostelSelect.required = false;
            purposesContainer.classList.add('hidden');
            gateContainer.classList.add('hidden');
            gateSelect.required = false;
        }
    });

    // -------------------------------------------------------------
    // closeUserModal()
    // Used to close the Register/Edit User modal and reset all form controls,
    // validation alerts, and profile photo previews
    // -------------------------------------------------------------
    function closeUserModal() {
        userModal.classList.add('hidden');
        userForm.reset();
        hostelContainer.classList.add('hidden');
        gateContainer.classList.add('hidden');
        purposesContainer.classList.add('hidden');
        formMessage.className = '';
        formMessage.textContent = '';
        if (typeof resetProfilePreview === 'function') {
            resetProfilePreview();
        }
        const profileImageInput = document.getElementById('user-profile-image-input');
        if (profileImageInput) {
            profileImageInput.value = '';
        }
    }

    // -------------------------------------------------------------
    // closeResetModal()
    // Used to close the Reset Password modal and clear form state
    // -------------------------------------------------------------
    function closeResetModal() {
        resetModal.classList.add('hidden');
        resetForm.reset();
        resetMessage.className = '';
        resetMessage.textContent = '';
    }

    // -------------------------------------------------------------
    // closeDeleteModal()
    // Used to close the Delete Confirmation modal and reset current ID
    // -------------------------------------------------------------
    function closeDeleteModal() {
        deleteModal.classList.add('hidden');
        deleteMessage.className = '';
        deleteMessage.textContent = '';
        targetDeleteUserId = null;
    }

    // -------------------------------------------------------------
    // Open Create Modal Event Listener
    // Attached to "Register New User" button in user_management.html
    // Prepares the form for a new registration (clearing ID, requiring password)
    // -------------------------------------------------------------
    const createBtn = document.getElementById('btn-create-user');
    if (createBtn) {
        createBtn.addEventListener('click', () => {
            formMode.value = 'create';
            userIdInput.value = '';
            modalTitle.textContent = 'Register New User';
            passwordInput.required = true;
            passwordLabel.textContent = 'Password *';
            passwordHelp.classList.add('hidden');
            saveUserBtn.querySelector('.btn-text').textContent = 'Save';
            
            userModal.classList.remove('hidden');
        });
    }

    // -------------------------------------------------------------
    // Cancel/Close Modal Button Binding
    // Linked to the close and cancel buttons of all modals in user_management.html
    // -------------------------------------------------------------
    document.getElementById('btn-close-user-modal').addEventListener('click', closeUserModal);
    document.getElementById('btn-cancel-user-modal').addEventListener('click', closeUserModal);
    document.getElementById('btn-close-reset-modal').addEventListener('click', closeResetModal);
    document.getElementById('btn-cancel-reset-modal').addEventListener('click', closeResetModal);
    document.getElementById('btn-close-delete-modal').addEventListener('click', closeDeleteModal);
    document.getElementById('btn-cancel-delete').addEventListener('click', closeDeleteModal);

    // -------------------------------------------------------------
    // Click Outside Modals Listener
    // Closes any open modal (User, Reset, Delete, or View Details) if clicking background overlay
    // -------------------------------------------------------------
    window.addEventListener('click', (e) => {
        if (e.target === userModal) closeUserModal();
        if (e.target === resetModal) closeResetModal();
        if (e.target === deleteModal) closeDeleteModal();
        if (e.target === document.getElementById('view-modal')) document.getElementById('view-modal').classList.add('hidden');
    });

    // -------------------------------------------------------------
    // Profile Image Upload Preview & Local Extension Validation
    // Used in user_management.html User modal profile upload block
    // Validates allowed file extensions (JPG, JPEG, PNG, WEBP)
    // -------------------------------------------------------------
    const profileImageInput = document.getElementById('user-profile-image-input');
    const profilePreviewImg = document.getElementById('profile-preview-img');
    const profilePreviewPlaceholder = document.getElementById('profile-preview-placeholder');

    if (profileImageInput) {
        profileImageInput.addEventListener('change', () => {
            const file = profileImageInput.files[0];
            if (file) {
                const allowedExtensions = ['jpg', 'jpeg', 'png', 'webp'];
                const fileExtension = file.name.split('.').pop().toLowerCase();
                if (!allowedExtensions.includes(fileExtension)) {
                    alert('Invalid file type! Only JPG, JPEG, PNG, and WEBP images are allowed.');
                    profileImageInput.value = '';
                    resetProfilePreview();
                    return;
                }

                const reader = new FileReader();
                reader.onload = (e) => {
                    profilePreviewImg.src = e.target.result;
                    profilePreviewImg.style.display = 'block';
                    profilePreviewPlaceholder.style.display = 'none';
                };
                reader.readAsDataURL(file);
            } else {
                resetProfilePreview();
            }
        });
    }

    // -------------------------------------------------------------
    // window.resetProfilePreview()
    // Clears the image preview src and restores the default placeholder
    // -------------------------------------------------------------
    window.resetProfilePreview = function() {
        if (profilePreviewImg) {
            profilePreviewImg.src = '';
            profilePreviewImg.style.display = 'none';
        }
        if (profilePreviewPlaceholder) {
            profilePreviewPlaceholder.style.display = 'block';
        }
    };

    // Close buttons inside View Details Modal in user_management.html
    document.getElementById('btn-close-view-modal').addEventListener('click', () => {
        document.getElementById('view-modal').classList.add('hidden');
    });
    document.getElementById('btn-cancel-view-modal').addEventListener('click', () => {
        document.getElementById('view-modal').classList.add('hidden');
    });

    // -------------------------------------------------------------
    // Open View Details Modal Event Listener
    // Attached to each table row's "View" button in system users table
    // Populates fields and sets up profile image/avatar placeholder
    // -------------------------------------------------------------
    document.querySelectorAll('.view-user-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.getElementById('view-full-name').textContent = btn.dataset.name;
            document.getElementById('view-username').textContent = btn.dataset.username;
            document.getElementById('view-email').textContent = btn.dataset.email;
            document.getElementById('view-contact').textContent = btn.dataset.contact || 'N/A';
            document.getElementById('view-department').textContent = btn.dataset.department || 'N/A';
            document.getElementById('view-role').textContent = btn.dataset.role;

            if (btn.dataset.role === 'Warden') {
                document.getElementById('view-hostel-container').classList.remove('hidden');
                document.getElementById('view-hostel').textContent = btn.dataset.hostel;
                document.getElementById('view-gate-container').classList.add('hidden');
            } else if (btn.dataset.role === 'Gatekeeper') {
                document.getElementById('view-gate-container').classList.remove('hidden');
                document.getElementById('view-gate').textContent = btn.dataset.gate;
                document.getElementById('view-hostel-container').classList.add('hidden');
            } else {
                document.getElementById('view-hostel-container').classList.add('hidden');
                document.getElementById('view-gate-container').classList.add('hidden');
            }

            // Display profile picture or text-initial placeholder
            const viewPic = document.getElementById('view-profile-pic');
            const viewPlaceholder = document.getElementById('view-profile-placeholder');
            if (btn.dataset.profile) {
                viewPic.src = btn.dataset.profile;
                viewPic.style.display = 'block';
                viewPlaceholder.style.display = 'none';
            } else {
                viewPic.style.display = 'none';
                viewPlaceholder.textContent = (btn.dataset.name || '?').substring(0, 1).toUpperCase();
                viewPlaceholder.style.display = 'flex';
            }
            
            // Map details to edit action button (moved from tables directly, nested inside details)
            const editFromViewBtn = document.getElementById('btn-edit-from-view');
            editFromViewBtn.dataset.id = btn.dataset.id;
            editFromViewBtn.dataset.name = btn.dataset.name;
            editFromViewBtn.dataset.username = btn.dataset.username;
            editFromViewBtn.dataset.email = btn.dataset.email;
            editFromViewBtn.dataset.contact = btn.dataset.contact || '';
            editFromViewBtn.dataset.department = btn.dataset.department || '';
            editFromViewBtn.dataset.role = btn.dataset.role;
            editFromViewBtn.dataset.hostel = btn.dataset.hostel || '';
            editFromViewBtn.dataset.gate = btn.dataset.gate || '';
            editFromViewBtn.dataset.purposes = btn.dataset.purposes || 'Emergency,Sunday Outing';
            editFromViewBtn.dataset.profile = btn.dataset.profile || '';
            
            document.getElementById('view-modal').classList.remove('hidden');
        });
    });

    // -------------------------------------------------------------
    // Open Edit Modal from View details button click
    // Closes view modal and opens the main User form in "Update" mode
    // -------------------------------------------------------------
    document.getElementById('btn-edit-from-view').addEventListener('click', () => {
        const btn = document.getElementById('btn-edit-from-view');
        document.getElementById('view-modal').classList.add('hidden');
        
        formMode.value = 'update';
        userIdInput.value = btn.dataset.id;
        modalTitle.textContent = 'Edit User';
        fullNameInput.value = btn.dataset.name;
        usernameInput.value = btn.dataset.username;
        emailInput.value = btn.dataset.email || '';
        document.getElementById('user-contact').value = btn.dataset.contact || '';
        document.getElementById('user-department').value = btn.dataset.department || '';
        passwordInput.required = false;
        passwordLabel.textContent = 'Password';
        passwordHelp.classList.remove('hidden');
        roleSelect.value = btn.dataset.role;

        // Sync visibility of Hostel vs Gate selectors
        roleSelect.dispatchEvent(new Event('change'));

        if (btn.dataset.role === 'Warden') {
            hostelSelect.value = btn.dataset.hostel;
            const purposesStr = btn.dataset.purposes || 'Emergency,Sunday Outing';
            const purposesArr = purposesStr.split(',');
            document.querySelectorAll('input[name="allowed_purposes"]').forEach(cb => {
                cb.checked = purposesArr.includes(cb.value);
            });
        } else if (btn.dataset.role === 'Gatekeeper') {
            gateSelect.value = btn.dataset.gate;
        }

        // Re-populate profile image preview if user already has one
        if (btn.dataset.profile) {
            profilePreviewImg.src = btn.dataset.profile;
            profilePreviewImg.style.display = 'block';
            profilePreviewPlaceholder.style.display = 'none';
        } else {
            resetProfilePreview();
        }

        saveUserBtn.querySelector('.btn-text').textContent = 'Update';
        userModal.classList.remove('hidden');
    });

    // -------------------------------------------------------------
    // Form Submit Event Handler (Create / Edit User)
    // Packages payload in a FormData object for backend multi-part uploading
    // Hits `/api/user/create/` or `/api/user/update/`
    // -------------------------------------------------------------
    userForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const btnText = saveUserBtn.querySelector('.btn-text');
        const spinner = saveUserBtn.querySelector('.spinner');

        formMessage.className = '';
        formMessage.textContent = '';

        // Front-end validation: Ensure contact is exactly 10 digits
        const contactVal = document.getElementById('user-contact').value.trim();
        if (contactVal.length < 10) {
            formMessage.className = 'message error';
            formMessage.textContent = 'Phone number must be exactly 10 digits.';
            return;
        }

        const passwordVal = passwordInput.value;

        // Build FormData
        const formData = new FormData();
        formData.append('id', userIdInput.value);
        formData.append('full_name', fullNameInput.value.trim());
        formData.append('username', usernameInput.value.trim());
        formData.append('email', emailInput.value.trim());
        formData.append('contact_number', contactVal);
        formData.append('department', document.getElementById('user-department').value);
        formData.append('password', passwordVal);
        formData.append('role', roleSelect.value);
        formData.append('hostel_name', hostelSelect.value);
        formData.append('gate_name', gateSelect.value);

        if (roleSelect.value === 'Warden') {
            const checkedPurposes = Array.from(document.querySelectorAll('input[name="allowed_purposes"]:checked')).map(cb => cb.value);
            if (checkedPurposes.length > 0) {
                formData.append('allowed_purposes', checkedPurposes.join(','));
            }
        }

        if (profileImageInput && profileImageInput.files[0]) {
            formData.append('profile_image', profileImageInput.files[0]);
        }

        const endpoint = formMode.value === 'create' ? '/api/user/create/' : '/api/user/update/';

        btnText.classList.add('hidden');
        spinner.classList.remove('hidden');
        saveUserBtn.disabled = true;

        try {
            const response = await fetch(endpoint, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': window.CSRF_TOKEN
                },
                body: formData
            });
            
            const data = await response.json();
            if (data.success) {
                formMessage.className = 'message success';
                formMessage.textContent = data.message;
                setTimeout(() => window.location.reload(), 1000);
            } else {
                formMessage.className = 'message error';
                formMessage.textContent = data.message || 'Error occurred while saving.';
                btnText.classList.remove('hidden');
                spinner.classList.add('hidden');
                saveUserBtn.disabled = false;
            }
        } catch (err) {
            formMessage.className = 'message error';
            formMessage.textContent = 'A network error occurred. Please try again.';
            btnText.classList.remove('hidden');
            spinner.classList.add('hidden');
            saveUserBtn.disabled = false;
        }
    });

    // -------------------------------------------------------------
    // Open Reset Password Dialog Event Listener
    // Triggered by "Reset" action button in user management table
    // -------------------------------------------------------------
    document.querySelectorAll('.reset-pw-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            resetUserId.value = btn.dataset.id;
            resetUsernameDisplay.textContent = `${btn.dataset.name} (${btn.dataset.id})`;
            resetModal.classList.remove('hidden');
        });
    });

    // -------------------------------------------------------------
    // Reset Password Form Submit Listener
    // Submits new password payload via POST to `/api/user/reset-password/`
    // -------------------------------------------------------------
    resetForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const btnText = savePwBtn.querySelector('.btn-text');
        const spinner = savePwBtn.querySelector('.spinner');

        resetMessage.className = '';
        resetMessage.textContent = '';

        const passwordVal = resetNewPw.value;
        const confirmPasswordVal = resetConfirmPw.value;

        if (passwordVal !== confirmPasswordVal) {
            resetMessage.className = 'message error';
            resetMessage.textContent = 'Passwords do not match!';
            return;
        }

        if (passwordVal.length < 6) {
            resetMessage.className = 'message error';
            resetMessage.textContent = 'Password must be at least 6 characters.';
            return;
        }

        const payload = {
            id: resetUserId.value,
            password: passwordVal,
            confirm_password: confirmPasswordVal
        };

        btnText.classList.add('hidden');
        spinner.classList.remove('hidden');
        savePwBtn.disabled = true;

        try {
            const response = await fetch('/api/user/reset-password/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': window.CSRF_TOKEN
                },
                body: JSON.stringify(payload)
            });
            
            const data = await response.json();
            if (data.success) {
                resetMessage.className = 'message success';
                resetMessage.textContent = data.message;
                setTimeout(() => window.location.reload(), 1000);
            } else {
                resetMessage.className = 'message error';
                resetMessage.textContent = data.message || 'Error updating password.';
                btnText.classList.remove('hidden');
                spinner.classList.add('hidden');
                savePwBtn.disabled = false;
            }
        } catch (err) {
            resetMessage.className = 'message error';
            resetMessage.textContent = 'Network error occurred.';
            btnText.classList.remove('hidden');
            spinner.classList.add('hidden');
            savePwBtn.disabled = false;
        }
    });

    // -------------------------------------------------------------
    // Open Delete Confirmation Modal Event Listener
    // Triggered by "Delete" action button in user management table
    // -------------------------------------------------------------
    document.querySelectorAll('.delete-user-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            targetDeleteUserId = btn.dataset.id;
            deleteUsernameDisplay.textContent = btn.dataset.name;
            deleteModal.classList.remove('hidden');
        });
    });

    // -------------------------------------------------------------
    // Delete Account Action Button Click Listener
    // Sends post request with user ID to `/api/user/delete/`
    // -------------------------------------------------------------
    confirmDeleteBtn.addEventListener('click', async () => {
        if (!targetDeleteUserId) return;
        const btnText = confirmDeleteBtn.querySelector('.btn-text');
        const spinner = confirmDeleteBtn.querySelector('.spinner');

        btnText.classList.add('hidden');
        spinner.classList.remove('hidden');
        confirmDeleteBtn.disabled = true;
        deleteMessage.className = '';
        deleteMessage.textContent = '';

        try {
            const response = await fetch('/api/user/delete/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': window.CSRF_TOKEN
                },
                body: JSON.stringify({ id: targetDeleteUserId })
            });
            
            const data = await response.json();
            if (data.success) {
                deleteMessage.className = 'message success';
                deleteMessage.textContent = data.message;
                setTimeout(() => window.location.reload(), 1000);
            } else {
                deleteMessage.className = 'message error';
                deleteMessage.textContent = data.message || 'Error deleting account.';
                btnText.classList.remove('hidden');
                spinner.classList.add('hidden');
                confirmDeleteBtn.disabled = false;
            }
        } catch (err) {
            deleteMessage.className = 'message error';
            deleteMessage.textContent = 'Network error occurred.';
            btnText.classList.remove('hidden');
            spinner.classList.add('hidden');
            confirmDeleteBtn.disabled = false;
        }
    });

    // -------------------------------------------------------------
    // Client-side Search / Filtering Event Listener
    // Filters user list table row entries on input query match
    // Matches against Name, Username, or Email columns
    // -------------------------------------------------------------
    const searchInput = document.getElementById('user-search');
    const tableBody = document.querySelector('#users-table tbody');

    if (searchInput && tableBody) {
        searchInput.addEventListener('input', () => {
            const searchTerm = searchInput.value.toLowerCase().trim();
            const rows = tableBody.querySelectorAll('tr');

            rows.forEach(row => {
                if (row.cells.length === 1 && row.cells[0].classList.contains('text-center')) return;

                const fullNameCell = row.querySelector('.user-full-name');
                const usernameCell = row.querySelector('.user-username');
                const emailCell = row.querySelector('.user-email');
                
                const fullName = fullNameCell ? fullNameCell.textContent.toLowerCase() : '';
                const username = usernameCell ? usernameCell.textContent.toLowerCase() : '';
                const email = emailCell ? emailCell.textContent.toLowerCase() : '';

                if (fullName.includes(searchTerm) || username.includes(searchTerm) || email.includes(searchTerm)) {
                    row.style.display = '';
                } else {
                    row.style.display = 'none';
                }
            });
        });
    }

    // Checkbox Selection Logic for System Users Table
    const userMasterCheckbox = document.getElementById('user-master-checkbox');
    const userTableBody = document.querySelector('#users-table tbody');

    if (userMasterCheckbox && userTableBody) {
        userMasterCheckbox.addEventListener('change', () => {
            const isChecked = userMasterCheckbox.checked;
            const rowCheckboxes = userTableBody.querySelectorAll('.user-row-checkbox');
            rowCheckboxes.forEach(cb => {
                cb.checked = isChecked;
            });
        });

        userTableBody.addEventListener('change', (e) => {
            if (e.target && e.target.classList.contains('user-row-checkbox')) {
                const rowCheckboxes = userTableBody.querySelectorAll('.user-row-checkbox');
                const checkedCheckboxes = userTableBody.querySelectorAll('.user-row-checkbox:checked');
                userMasterCheckbox.checked = (rowCheckboxes.length > 0 && rowCheckboxes.length === checkedCheckboxes.length);
            }
        });
    }

    // Password Visibility Toggle Logic
    const bindPasswordToggles = () => {
        document.querySelectorAll('.password-toggle-btn').forEach(btn => {
            if (btn.dataset.bound) return;
            btn.dataset.bound = "true";
            btn.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                const input = btn.parentElement.querySelector('input');
                const icon = btn.querySelector('i');
                if (input && icon) {
                    if (input.type === 'password') {
                        input.type = 'text';
                        icon.classList.remove('fa-eye');
                        icon.classList.add('fa-eye-slash');
                    } else {
                        input.type = 'password';
                        icon.classList.remove('fa-eye-slash');
                        icon.classList.add('fa-eye');
                    }
                }
            });
        });
    };
    bindPasswordToggles();
});

