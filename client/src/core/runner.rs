use std::thread::{self, JoinHandle};

/// Spawns the `/process` request on a worker thread so the main loop never
/// blocks on the network (CLI-05). Returns as soon as the thread is spawned.
pub fn spawn_processing<F>(f: F) -> JoinHandle<()>
where
    F: FnOnce() + Send + 'static,
{
    thread::spawn(f)
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::mpsc;
    use std::sync::{Arc, Mutex};
    use std::time::Duration;

    #[test]
    fn spawn_returns_while_closure_is_still_blocked() {
        let (unblock_tx, unblock_rx) = mpsc::channel::<()>();
        let (done_tx, done_rx) = mpsc::channel::<()>();

        let handle = spawn_processing(move || {
            unblock_rx.recv().expect("unblock signal");
            done_tx.send(()).ok();
        });

        // CLI-05: the main thread returned while the worker is blocked.
        assert!(
            done_rx.try_recv().is_err(),
            "closure must not have completed before being unblocked"
        );

        unblock_tx.send(()).expect("unblock signal accepted");
        done_rx.recv().expect("closure finished");
        handle.join().expect("worker thread joined");
    }

    #[test]
    fn spawned_closure_runs_to_completion_on_separate_thread() {
        let flag = Arc::new(Mutex::new(false));
        let flag_clone = Arc::clone(&flag);
        let (tx, rx) = mpsc::channel::<()>();

        let handle = spawn_processing(move || {
            *flag_clone.lock().unwrap() = true;
            tx.send(()).ok();
        });

        rx.recv_timeout(Duration::from_secs(5))
            .expect("closure signalled completion");
        handle.join().expect("worker thread joined");
        assert!(*flag.lock().unwrap(), "closure ran to completion");
    }
}
