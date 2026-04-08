const { reactive } = window.Vue;

function createRoleShell(role = "") {
    return {
        role,
        title: "",
        copy: "",
        navItems: [],
        summaryItems: [],
        controls: null,
    };
}

const shellState = reactive({
    student: createRoleShell("student"),
    teacher: createRoleShell("teacher"),
    admin: createRoleShell("admin"),
});

function assignRoleShell(target, next = {}) {
    const base = createRoleShell(target.role);
    Object.assign(target, base, next);
}

export function useWorkspaceShell() {
    const getRoleShell = (role = "") => shellState[role] || createRoleShell(role);

    const setRoleShell = (role, next = {}) => {
        if (!shellState[role]) {
            shellState[role] = createRoleShell(role);
        }
        assignRoleShell(shellState[role], next);
        return shellState[role];
    };

    const resetRoleShell = (role) => {
        if (!shellState[role]) return;
        assignRoleShell(shellState[role], {});
    };

    return {
        shellState,
        getRoleShell,
        setRoleShell,
        resetRoleShell,
    };
}
