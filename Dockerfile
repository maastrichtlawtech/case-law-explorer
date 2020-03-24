FROM linuxconfig/lemp
MAINTAINER Pedro V Hernandez Serrano <p.hernandezserrano@maastrichtuniversity.nl>

RUN apt-get update
RUN apt-get -y install mariadb-server
RUN sed -i 's/bind-address/#bind-address/' /etc/mysql/mariadb.conf.d/50-server.cnf
RUN sed -i 's/index.php/index.html/' /etc/nginx/sites-available/default

RUN service mysql start; mysql -u root -e "CREATE OR REPLACE DATABASE case_law;USE case_law;";

RUN apt-get clean

EXPOSE 80 3306

CMD ["supervisord"]