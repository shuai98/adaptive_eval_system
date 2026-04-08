const { ref } = window.Vue;

export function useTaskPoller() {
    const polling = ref(false);

    const sleep = (delay) => new Promise((resolve) => window.setTimeout(resolve, delay));

    const pollTask = async ({ scope, taskId, interval = 900, onProgress, onSuccess }) => {
        polling.value = true;
        try {
            while (true) {
                const payload = await window.AppApi.requestJson(`/${scope}/tasks/${taskId}`);
                if (payload.status !== "success") {
                    throw new Error(payload.detail || "任务状态获取失败");
                }

                const task = payload.data;
                onProgress?.(task);

                if (task.status === "success") {
                    await onSuccess?.(task.result);
                    return task.result;
                }

                if (["failed", "cancelled", "timeout"].includes(task.status)) {
                    throw new Error(task.error_message || "任务执行失败");
                }

                await sleep(interval);
            }
        } finally {
            polling.value = false;
        }
    };

    return {
        polling,
        pollTask,
    };
}
