import { useTranslation } from "react-i18next";
import { useSearchParams } from "react-router-dom";
import PageLayout from "@/components/common/pageLayout";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useDocumentTitle } from "@/hooks/use-document-title";
import AdminUsersPage from "@/pages/admin-users/admin-users-page";
import { TeamManagement } from "@/pages/TeamsPage/components/team-management";

export default function AdminPage() {
  const { t } = useTranslation();
  const [searchParams, setSearchParams] = useSearchParams();
  const tab = searchParams.get("tab") === "teams" ? "teams" : "users";
  useDocumentTitle(t("adminUsers.title"));

  return (
    <main className="flex w-full min-w-0 flex-1">
      <PageLayout
        title={t("adminUsers.title")}
        description={t("adminUsers.pageDescription")}
        backTo="/"
      >
        <Tabs
          value={tab}
          onValueChange={(value) => {
            setSearchParams((current) => {
              const next = new URLSearchParams(current);
              if (value === "teams") next.set("tab", "teams");
              else next.delete("tab");
              return next;
            });
          }}
          className="flex w-full min-w-0 flex-col"
        >
          <TabsList
            aria-label={t("adminUsers.title")}
            className="justify-start border-b"
          >
            <TabsTrigger
              value="users"
              className="px-5 focus-visible:outline focus-visible:outline-2 focus-visible:outline-ring motion-reduce:transition-none"
            >
              {t("adminUsers.usersTitle")}
            </TabsTrigger>
            <TabsTrigger
              value="teams"
              className="px-5 focus-visible:outline focus-visible:outline-2 focus-visible:outline-ring motion-reduce:transition-none"
            >
              {t("authz.navigation.teams")}
            </TabsTrigger>
          </TabsList>
          <TabsContent value="users" className="mt-6 min-w-0">
            <AdminUsersPage />
          </TabsContent>
          <TabsContent value="teams" className="mt-6 min-w-0">
            <TeamManagement adminMode layout="panel" />
          </TabsContent>
        </Tabs>
      </PageLayout>
    </main>
  );
}
