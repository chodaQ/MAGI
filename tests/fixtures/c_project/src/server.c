#include <sys/socket.h>
#include <netinet/in.h>
#include <pthread.h>
#include <stdio.h>
#include <sys/mman.h>
#include <unistd.h>

void *handle_client(void *arg) {
    int client_fd = *(int *)arg;
    char buf[256];
    recv(client_fd, buf, sizeof(buf), 0);
    send(client_fd, "ok", 2, 0);
    return NULL;
}

int main(void) {
    int fd = socket(AF_INET, SOCK_STREAM, 0);
    struct sockaddr_in addr = { .sin_family = AF_INET };
    bind(fd, (struct sockaddr *)&addr, sizeof(addr));
    listen(fd, 16);

    int client = accept(fd, NULL, NULL);
    pthread_t tid;
    pthread_create(&tid, NULL, handle_client, &client);
    pthread_join(tid, NULL);

    FILE *log = fopen("/var/log/server.log", "a");
    fwrite("started\n", 1, 8, log);
    fclose(log);

    void *shared = mmap(NULL, 4096, PROT_READ | PROT_WRITE, MAP_SHARED, -1, 0);
    (void)shared;

    close(fd);
    return 0;
}
